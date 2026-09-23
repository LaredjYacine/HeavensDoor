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
@limiter.limit("1000/minute")
def agent(
    request: Request, query: str, idempotency_id: str | None = None
):  # , response_class=EventSourceResponse):
    try:
        if idempotency_id is None:
            idempotency_id = str(uuid.uuid4())
        claimed = client.set(
            f"idem_id : {idempotency_id}", "pending", nx=True, ex=86400
        )
        if not claimed:
            job_id = client.get(f"idem_id : {idempotency_id}")

            return {
                "status": "Duplicate",
                "job_id": job_id,
                "idempotency_id": idempotency_id,
                "message": "Job already submitted before",
            }
        task = celery_app.send_task("agent", args=[query])
        client.set(f"idem_id : {idempotency_id}", task.id, ex=86400)
        return {
            "job_id": task.id,
            "status": "202 Accepted",
            "idempotency_key": idempotency_id,
            "message": "job Submitted go to /result ",
        }
    except ValueError as e:
        return {"status": "Error", "message": str(e)}

    except Exception as e:  # noqa: BLE001
        return {"status": "Error", "message": str(e)}


@route.get("/result")
@limiter.limit("10000/minute")
def result(request: Request, job_id: str):
    try:
        data = client.get(f"job_id : {job_id}")
        if data:
            data_json = json.loads(data)
            if data_json:
                return data_json
        result = celery_app.AsyncResult(job_id, app=celery_app)
        if result.ready():
            print(type(result.result))
            if isinstance(result.result, list):
                data = ",".join(result.result)
        raw_data = {"job_id": job_id, "state": result.state, "result": data}
        if result.state == "SUCCESS":
            client.set(f"job_id:{job_id}", json.dumps(raw_data), ex=3600)
        return raw_data
    except ValueError as e:
        return {"status": "Error", "message": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "Error", "message": str(e)}
