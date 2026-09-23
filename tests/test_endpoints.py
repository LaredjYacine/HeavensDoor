"""Endpoint tests for Heaven's Door.

Runs against the real FastAPI app via TestClient, with Redis and Celery
mocked so no external service is required.
"""

import json

# ---------------------------------------------------------------------------
# Pages & static assets
# ---------------------------------------------------------------------------


def test_home_page_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Heaven's Door" in response.text


def test_about_page_served(client):
    response = client.get("/about")
    assert response.status_code == 200
    assert "About Heaven's Door" in response.text


def test_frontend_assets_served(client):
    for path, content_types in [
        ("/static/Front.css", ("text/css",)),
        ("/static/script.js", ("text/javascript", "application/javascript")),
        ("/static/Front.html", ("text/html",)),
    ]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["content-type"].split(";")[0] in content_types, path


def test_icon_served(client):
    response = client.get("/static/icon.png")
    assert response.status_code == 200
    assert "image" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# POST /agent
# ---------------------------------------------------------------------------


def test_agent_submits_job(client, celery_fake):
    celery_fake._state = "PENDING"

    response = client.post("/agent?query=frontend%20developer")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "202 Accepted"
    assert body["job_id"] == "test-job-id"
    assert body["idempotency_key"]
    assert "message" in body


def test_agent_generates_idempotency_key_when_missing(client):
    response = client.post("/agent?query=backend")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "202 Accepted"
    assert body["idempotency_key"]


def test_agent_dedupes_repeated_idempotency_key(client, redis_fake):
    redis_fake.store["idem_id : dup-key"] = "existing-job-id"

    response = client.post("/agent?query=python&idempotency_id=dup-key")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Duplicate"
    assert body["job_id"] == "existing-job-id"


# ---------------------------------------------------------------------------
# GET /result
# ---------------------------------------------------------------------------


def test_result_success(client, celery_fake):
    celery_fake._state = "SUCCESS"
    celery_fake._result = ["Senior Frontend Engineer"]

    response = client.get("/result?job_id=test-job-id")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "SUCCESS"
    assert "Senior Frontend Engineer" in body["result"]


def test_result_pending(client, celery_fake):
    celery_fake._state = "PENDING"
    celery_fake._result = None

    response = client.get("/result?job_id=test-job-id")

    assert response.status_code == 200
    assert response.json()["state"] == "PENDING"


def test_result_failure(client, celery_fake):
    celery_fake._state = "FAILURE"
    celery_fake._result = None

    response = client.get("/result?job_id=test-job-id")

    assert response.status_code == 200
    assert response.json()["state"] == "FAILURE"


def test_result_reads_cached_value(client, redis_fake):
    cached = json.dumps(
        {"job_id": "abc-123", "state": "SUCCESS", "result": "Cached answer"}
    )
    redis_fake.store["job_id : abc-123"] = cached

    response = client.get("/result?job_id=abc-123")

    assert response.status_code == 200
    assert response.json()["result"] == "Cached answer"
