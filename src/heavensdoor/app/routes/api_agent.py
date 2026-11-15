import json
import uuid

from fastapi import APIRouter
from fastapi.requests import Request
from upstash_redis import Redis

from heavensdoor.app.services.celery import celery_app

from ..services.limiter import limiter

client = Redis.from_env()


route = APIRouter()


@route.post("/agent")
@limiter.limit("10/minute")
def agent(
    request: Request,
    query: str,
    idempotency_id: str | None = None,
    session_id: str | None = None,
):  # , response_class=EventSourceResponse):
    try:
        if idempotency_id is None:
            idempotency_id = str(uuid.uuid4())
        claimed = client.set(
            f"idem_id : {idempotency_id}", "pending", nx=True, ex=86400
        )
        if not claimed:
            existing = client.get(f"idem_id : {idempotency_id}")
            return {
                "status": "Duplicate",
                "job_id": existing,
                "idempotency_id": idempotency_id,
                "message": "Job already submitted before",
            }
        task = celery_app.send_task("agent", args=[session_id, query])
        client.set(f"idem_id : {idempotency_id}", task.id, ex=86400)
        return {
            "job_id": task.id,
            "status": "202 Accepted",
            "idempotency_key": idempotency_id,
            "message": "job Submitted go to /result ",
        }
    except Exception as e:  # noqa: BLE001
        # Clean up idempotency key so retries don't get stuck on "pending"
        client.delete(f"idem_id : {idempotency_id}")
        return {"status": "Error", "message": str(e)}


@route.get("/result")
@limiter.limit("10/minute")
def result(request: Request, job_id: str):
    try:
        # 1) Fast path: cached response in Redis
        data = client.get(f"job_id:{job_id}")
        if data:
            return json.loads(data)

        # 2) Fallback: ask Celery for the task state
        task = celery_app.AsyncResult(job_id, app=celery_app)
        if task.ready():
            task_result = task.result
            # Normalise anything Celery may return to a list[str]
            if isinstance(task_result, list):
                output = task_result
            elif isinstance(task_result, str):
                output = [task_result]
            elif task_result is None:
                output = []
            else:
                output = [str(task_result)]

            state = task.state
            if state == "SUCCESS":
                raw_data = {"job_id": job_id, "state": state, "result": output}
                client.set(f"job_id:{job_id}", json.dumps(raw_data), ex=3600)
                return raw_data

            return {"job_id": job_id, "state": state, "result": output}

        # 3) Still running
        return {"job_id": job_id, "state": "PENDING", "result": []}

    except Exception as e:  # noqa: BLE001
        return {"status": "Error", "message": str(e)}
