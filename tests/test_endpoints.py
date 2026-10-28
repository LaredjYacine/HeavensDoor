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
    redis_fake.store["job_id:abc-123"] = cached

    response = client.get("/result?job_id=abc-123")

    assert response.status_code == 200
    assert response.json()["result"] == "Cached answer"


BODY = {"query": "frontend developer", "session_id": "sess-1"}


# ---------------- POST /v2/agent ----------------


def test_v2_agent_submits_job(v2client, celery_fake, redis_fake):
    response = v2client.post("/v2/agent", json=BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["Status"] == "202 Accepted"
    assert body["job_id"] == "test-job-id"
    assert body["idempotency_key"]
    assert "message" in body
    assert celery_fake.calls[0] == ("stream", ("sess-1", "frontend developer"))
    assert f"idem_id : {body['idempotency_key']}" in redis_fake.store


def test_v2_agent_generates_idempotency_key_when_missing(v2client):
    response = v2client.post("/v2/agent", json={"query": "backend", "session_id": "s"})

    assert response.status_code == 200
    assert response.json()["idempotency_key"]


def test_v2_agent_dedupes_repeated_idempotency_key(v2client, redis_fake):
    redis_fake.store["idem_id : dup-key"] = "existing-job-id"

    response = v2client.post("/v2/agent", json={**BODY, "idempotency_key": "dup-key"})

    body = response.json()
    assert body["Status"] == "Duplicate"
    assert body["job_id"] == "existing-job-id"


def test_v2_agent_second_call_returns_first_job_id(v2client):
    # fails until you store task.id instead of "pending"
    first = v2client.post("/v2/agent", json={**BODY, "idempotency_key": "k1"}).json()
    second = v2client.post("/v2/agent", json={**BODY, "idempotency_key": "k1"}).json()

    assert second["Status"] == "Duplicate"
    assert second["job_id"] == first["job_id"]


def test_v2_agent_missing_query_is_rejected(v2client):
    response = v2client.post("/v2/agent", json={"session_id": "s"})
    assert response.status_code == 422


def test_v2_agent_reports_celery_error(v2client, celery_fake):
    def boom(*a, **k):
        raise RuntimeError("broker down")

    celery_fake.send_task = boom

    body = v2client.post("/v2/agent", json=BODY).json()

    assert body["Status"] == "Error"
    assert "broker down" in body["message"]


# ---------------- GET /v2/result (non-stream) ----------------


def test_v2_result_success(v2client, celery_fake):
    celery_fake._state = "SUCCESS"
    celery_fake._result = ["Senior Frontend Engineer"]

    body = v2client.get("/v2/result?job_id=test-job-id").json()

    assert body["status"] == "202 Accepted"
    assert body["job_id"] == "test-job-id"
    assert "Senior Frontend Engineer" in body["result"]


def test_v2_result_pending(v2client, celery_fake):
    celery_fake._state = "PENDING"

    body = v2client.get("/v2/result?job_id=test-job-id").json()

    assert body["status"] == "PENDING"


def test_v2_result_failure(v2client, celery_fake):
    celery_fake._state = "FAILURE"

    body = v2client.get("/v2/result?job_id=test-job-id").json()

    assert body["status"] == "Error"


# ---------------- GET /v2/result (streaming) ----------------


def _parse_sse(text):
    return [
        json.loads(line[len("data: ") :])
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


def test_v2_result_streams_tokens(v2client, redis_fake):
    redis_fake.xadd("job-1", "1-0", {"token": "Hel", "done": "false"})
    redis_fake.xadd("job-1", "2-0", {"token": "lo", "done": "false"})
    redis_fake.xadd("job-1", "3-0", {"token": "[DONE]", "done": "true"})

    with v2client.stream("GET", "/v2/result?job_id=job-1") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse("".join(response.iter_text()))

    assert [e["token"] for e in events] == ["Hel", "lo", "[DONE]"]
    assert events[-1]["done"] is True


def test_v2_result_stream_handles_list_shaped_entries(v2client, redis_fake):
    # Upstash can return entries as a flat list ["token", "hi", "done", "true"]
    redis_fake.xadd("job-2", "1-0", ["token", "hi", "done", "true"])

    with v2client.stream("GET", "/v2/result?job_id=job-2") as response:
        events = _parse_sse("".join(response.iter_text()))

    assert events == [{"token": "hi", "done": True}]


def test_v2_result_stream_skips_entries_without_token(v2client, redis_fake):
    redis_fake.xadd("job-3", "1-0", {"junk": "x"})
    redis_fake.xadd("job-3", "2-0", {"token": "ok", "done": "true"})

    with v2client.stream("GET", "/v2/result?job_id=job-3") as response:
        events = _parse_sse("".join(response.iter_text()))

    assert [e["token"] for e in events] == ["ok"]


def test_v2_result_does_not_stream_when_no_entries(v2client, celery_fake):
    celery_fake._state = "PENDING"

    response = v2client.get("/v2/result?job_id=unknown")

    assert not response.headers["content-type"].startswith("text/event-stream")
