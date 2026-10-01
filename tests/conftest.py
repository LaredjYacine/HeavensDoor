"""Shared test setup.

Keeps the whole suite hermetic: the app imports with dummy credentials and
both Redis (Upstash) and Celery are replaced with in-memory fakes, so no
external service is ever contacted — perfect for CI.
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import supabase
from dotenv import dotenv_values
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)

# Dummy credentials — set before app modules are imported
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


# Captured before the factory is stubbed out, so live tests can still build a
# genuine client from the real credentials.
_REAL_CREATE_CLIENT = supabase.create_client

supabase.create_client = _DummySupabaseClient

# --- ONLY the app-specific import stays down here after environment setup ---
from heavensdoor.app.routes import Apiagent


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


def _swap_supabase_client(new_client: Any) -> list[Any]:
    """Point every module still holding a dummy client at ``new_client``.

    Modules use ``from .credentials import supabase_client``, which copies the
    value into their own namespace at import time. Patching ``credentials``
    alone is therefore not enough: each importer keeps a private reference to
    the dummy it captured. Matching is by type, not identity, because the
    stubbed factory builds a fresh instance on every call.
    """
    swapped: list[Any] = []
    for module in list(sys.modules.values()):
        if isinstance(getattr(module, "supabase_client", None), _DummySupabaseClient):
            try:
                module.supabase_client = new_client  # type: ignore[attr-defined]
                swapped.append(module)
            except (AttributeError, TypeError):
                continue
    return swapped


@pytest.fixture(autouse=True)
def _supabase_client_for_scope(request):
    """Give live tests a real Supabase client; leave the endpoint suite offline.

    ``test_endpoints.py`` asserts on hermetic behaviour, so it keeps the dummy.
    Every other module (currently ``test_RagEval.py``) reads real credentials
    so retrieval reflects production data.
    """
    if request.module.__name__.endswith("test_endpoints"):
        yield
        return

    credentials = dotenv_values(REPO_ROOT / ".env")
    url = credentials.get("supabase_url")
    key = credentials.get("supabase_Key")
    if not url or not key:
        pytest.skip("Supabase credentials are not configured in .env")

    real_client = _REAL_CREATE_CLIENT(url, key)
    _swap_supabase_client(real_client)
    try:
        yield
    finally:
        _swap_supabase_client(_DummySupabaseClient())


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


test_results = {"passed": 0, "failed": 0}


def pytest_runtest_logreport(report):
    if report.when == "call" and "test_RagEval.py" in report.nodeid:
        if report.passed:
            test_results["passed"] += 1
        else:
            test_results["failed"] += 1


def pytest_sessionfinish(session, exitstatus):
    total = test_results["passed"] + test_results["failed"]
    if total == 0:
        return
    baseline = 1.0
    current_success_rate = test_results["passed"] / total
    print(
        f"Passed: {test_results['passed']}/{total} ({current_success_rate * 100:.1f}%)"
    )
    allowed_drop = 0.20
    if current_success_rate < baseline - allowed_drop:
        print(f"Failed: {current_success_rate * 100:.1f}% (below baseline)")
        session.exitstatus = 1
    else:
        print("the Rag Eval was a Sucess")
