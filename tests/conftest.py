"""Shared test setup.

Keeps the whole suite hermetic: the app imports with dummy credentials and
both Redis (Upstash) and Celery are replaced with in-memory fakes, so no
external service is ever contacted — perfect for CI.
"""

import os
import sys
from pathlib import Path
from typing import Any
import supabase
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from heavensdoor.app.routes import Apiagent

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)

# Read the real credentials from .env without touching os.environ, so they can be
# handed to the live tests below. dotenv_values() only parses; it does not export.
_REAL_ENV: dict[str, str] = {}
try:
    from dotenv import dotenv_values

    _REAL_ENV = {
        key: value for key, value in dotenv_values(REPO_ROOT / ".env").items() if value
    }
except Exception:  # noqa: BLE001 - a missing .env just means no live tests
    _REAL_ENV = {}

# The hermetic endpoint suite is the only thing that must never touch the network.
# Everything else (notably the RAG eval) gets the genuine Supabase client, so
# scoring against a dummy would be meaningless.
_HERMETIC_MODULES = frozenset({"test_endpoints.py"})

# Dummy credentials — enough for the app to import without real environment.
# Set before the app modules are imported (dotenv does not override them).
os.environ.setdefault("supabase_url", "https://supabase.invalid")
os.environ.setdefault("supabase_Key", "test-supabase-key")
os.environ.setdefault("groq", "test-groq-key")
os.environ.setdefault("redisurl", "redis://localhost:6379/0")
os.environ.setdefault("backendurl", "http://testserver")
os.environ.setdefault("UPSTASH_REDIS_REST_URL", "https://dummy.upstash.invalid")
os.environ.setdefault("UPSTASH_REDIS_REST_TOKEN", "test-upstash-token")

# Keep Supabase client creation off the network at import time.


class _DummySupabaseClient:
    def __init__(self, *args, **kwargs):
        pass


# Keep a handle on the real factory. The hermetic endpoint suite never needs it,
# but the live RAG eval in test_RagEval.py queries real Supabase and has no other
# way to reach the genuine implementation once the attribute below is replaced.
REAL_CREATE_CLIENT = supabase.create_client

supabase.create_client = _DummySupabaseClient

# Must happen after the environment is prepared.


def _is_hermetic(node: pytest.Item) -> bool:
    """True for the tests that must stay offline (the endpoint suite)."""
    return Path(str(node.fspath)).name in _HERMETIC_MODULES


@pytest.fixture(autouse=True)
def _supabase_client_for_scope(request: pytest.FixtureRequest):
    """Hand the endpoint suite a dummy client, live tests the real one.

    The dummy keeps test_endpoints.py hermetic so CI never contacts Supabase.
    The RAG eval scores the real retriever, so it needs a genuine client built
    from the real .env credentials rather than the dummy placeholders set above.
    """
    if _is_hermetic(request.node):
        yield
        return

    if not _REAL_ENV:
        pytest.skip(
            "live tests need real .env credentials (supabase_url, supabase_Key)"
        )

    from heavensdoor.app.services import credentials

    url = _REAL_ENV.get("supabase_url")
    key = _REAL_ENV.get("supabase_Key")
    if not url or not key:
        pytest.skip("live tests need supabase_url and supabase_Key in .env")

    # Assign the client rather than reloading credentials: reloading re-runs the
    # module-level validation against the placeholder env vars set at the top of
    # this file, and the module binds its client at import time.
    real_client = REAL_CREATE_CLIENT(url, key)
    credentials.supabase_client = real_client

    # Search_function.py does ``from .credentials import supabase_client``, so it
    # captured the dummy into its own namespace at import time. Patching only
    # credentials would leave that stale reference in place, which is why the
    # eval still hit '_DummySupabaseClient' object has no attribute 'rpc'.
    # Every already-imported module holding that name has to be updated too.
    def swap(new_client: Any) -> list[Any]:
        """Point every module holding the dummy at ``new_client``."""
        swapped: list[Any] = []
        for module in list(sys.modules.values()):
            # Match on type, not identity: credentials.py calls the stubbed
            # factory, which builds a fresh instance, so it is never the same
            # object as a reference saved earlier.
            if isinstance(
                getattr(module, "supabase_client", None), _DummySupabaseClient
            ):
                try:
                    module.supabase_client = new_client  # type: ignore[attr-defined]
                    swapped.append(module)
                except (AttributeError, TypeError):
                    continue
        return swapped

    swap(real_client)
    try:
        yield
    finally:
        swap(_DummySupabaseClient())


class FakeRedis:
    """In-memory stand-in for the Upstash REST client."""

    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def rpush(self, *args):
        return 1


class FakeAsyncResult:
    def __init__(self, state, result):
        self.state = state
        self.result = result

    def ready(self):
        return True


class FakeCelery:
    def __init__(self, state="SUCCESS", result=None):
        self._state = state
        self._result = result

    def _task(self):
        return SimpleNamespace(id="test-job-id")

    def send_task(self, name, args=None, **kwargs):
        return self._task()

    def AsyncResult(self, job_id, app=None):
        return FakeAsyncResult(self._state, self._result)


@pytest.fixture
def redis_fake():
    return FakeRedis()


@pytest.fixture
def celery_fake():
    return FakeCelery(state="SUCCESS", result=["Test match"])


@pytest.fixture
def client(monkeypatch, redis_fake, celery_fake):
    from heavensdoor.app.main import app

    monkeypatch.setattr(Apiagent, "client", redis_fake)
    monkeypatch.setattr(Apiagent, "celery_app", celery_fake)

    with TestClient(app) as test_client:
        yield test_client
