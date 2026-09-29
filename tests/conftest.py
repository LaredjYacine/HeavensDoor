"""Shared test setup.

Keeps the whole suite hermetic: the app imports with dummy credentials and
both Redis (Upstash) and Celery are replaced with in-memory fakes, so no
external service is ever contacted — perfect for CI.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)

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
import supabase  # noqa: E402


class _DummySupabaseClient:
    def __init__(self, *args, **kwargs):
        pass


# Keep a handle on the real factory. The hermetic endpoint suite never needs it,
# but the live RAG eval in test_RagEval.py queries real Supabase and has no other
# way to reach the genuine implementation once the attribute below is replaced.
REAL_CREATE_CLIENT = supabase.create_client


supabase.create_client = _DummySupabaseClient

# Must happen after the environment is prepared.
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from heavensdoor.app.routes import Apiagent  # noqa: E402


@pytest.fixture(autouse=True)
def _real_supabase_for_rag_eval(request: pytest.FixtureRequest):
    """Give ``rag_eval`` tests the genuine Supabase client, others the dummy.

    The dummy is what keeps the endpoint suite hermetic and offline, but the RAG
    eval scores the real retriever, so a stubbed client would make its numbers
    meaningless. Restoring is scoped to marked tests and undone afterwards, so
    the endpoint suite still never touches the network.
    """
    if request.node.get_closest_marker("rag_eval") is None:
        yield
        return

    from heavensdoor.app.services import credentials

    # Patch the already-constructed client on the credentials module rather than
    # reloading it: reloading re-runs the module-level credential validation
    # against the dummy environment that conftest set up for the hermetic suite,
    # which raises before it ever gets to build a client.
    credentials.supabase_client = REAL_CREATE_CLIENT(
        os.environ["supabase_url"], os.environ["supabase_Key"]
    )
    try:
        yield
    finally:
        credentials.supabase_client = _DummySupabaseClient()


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
