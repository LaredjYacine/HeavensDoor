import json
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from upstash_redis import Redis

from ..services.celery import celery_app
from ..services.credentials import AgentRequest
from ..services.limiter import limiter

redis = Redis.from_env()
stream_router = APIRouter(prefix="/v2")


def stream_result(job_id):
    last_id = "0-0"
    max_empty_polls = 60
    empty_polls = 0

    while empty_polls < max_empty_polls:
        try:
            stream = redis.xread({job_id: last_id}, count=10)
        except Exception:  # noqa: BLE001 - process boundary: convert any failure into a DLQ recor
            stream = None

        if not stream:
            empty_polls += 1
            time.sleep(0.5)
            continue

        empty_polls = 0
        for stream_name, messages in stream:
            for message_id, data in messages:
                last_id = message_id

                # Safely normalize data whether Upstash returns a dict or a list
                if isinstance(data, list):
                    data_dict = {data[i]: data[i + 1] for i in range(0, len(data), 2)}
                elif isinstance(data, dict):
                    data_dict = data
                else:
                    continue

                token = data_dict.get("token")
                if not token:
                    continue

                payload = json.dumps({"token": token})
                yield f"data: {payload}\n\n"

                if token == "[DONE]":
                    return


@stream_router.post("/agent")
@limiter.limit("1000/minute")
async def agent(request: Request, body: AgentRequest):
    idempotency_key = body.idempotency_key
    query = body.query
    session_id = body.session_id
    if not idempotency_key:
        idempotency_key = str(uuid.uuid4())
    try:
        claimed = redis.set(f"idem_id:{idempotency_key}", "pending", nx=True, ex=3600)
        if not claimed:
            job_id = redis.get(f"idem_id:{idempotency_key}")
            return {
                "Status": "Duplicate",
                "job_id": job_id,
                "idempotency_key": idempotency_key,
                "message": "Duplicate request. Job is already in progress.",
            }
        task = celery_app.send_task("stream", args=(session_id, query))
        return {
            "Status": "Success",
            "job_id": task.id,
            "idempotency_key": idempotency_key,
            "message": "Task submitted successfully.",
        }
    except ValueError as e:
        return {"Status": "Error Has Occured", "message": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"Status": "Error", "message": str(e)}


@stream_router.get("/result")
@limiter.limit("1000/minute")
async def result(request: Request, job_id: str):
    try:
        entries = redis.xrange(job_id, "-", "+")
        if entries:
            return StreamingResponse(
                stream_result(job_id), media_type="text/event-stream"
            )

        celery_result = celery_app.AsyncResult(job_id)
        if celery_result.ready():
            result = celery_result.get()
            return {"Status": "Success", "job_id": job_id, "result": result}
        else:
            return {
                "Status": "Pending",
                "job_id": job_id,
                "message": "Task is still in progress.",
            }

    except Exception as e:  # noqa: BLE001
        return {"Status": "Error", "message": str(e)}
