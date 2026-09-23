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
import supabase


class _DummySupabaseClient:
    def __init__(self, *args, **kwargs):
        pass


supabase.create_client = _DummySupabaseClient

# Must happen after the environment is prepared.
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

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
