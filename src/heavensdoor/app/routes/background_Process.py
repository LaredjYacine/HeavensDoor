import json
import pprint
import time

import httpx
from celery.exceptions import MaxRetriesExceededError
from fastapi import HTTPException, status
from huggingface_hub.errors import BadRequestError
from langchain.messages import HumanMessage
from langgraph.errors import GraphRecursionError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from upstash_redis import Redis

from ..services.agent import llm
from ..services.celery import celery_app
from ..services.langfuse_setup import start_agent_trace
from ..services.Logger import JsonLlmLogger
from ..services.SSL_fix import Finetuned

client = Redis.from_env()


def streaming(messages):
    for chunk in messages:
        if chunk.get("type") == "messages":
            message, _ = chunk["data"]
            yield message.content


@retry(
    stop=stop_after_attempt(4),  # Try up to 4 times
    wait=wait_exponential(
        multiplier=2, min=2, max=10
    ),  # Wait 2s, 4s, 8s... between tries
    retry=retry_if_exception_type((BadRequestError, httpx.HTTPStatusError, Exception)),
    reraise=True,  # Raise the final error if all retries fail
)
def run_agent_safely(
    payload,
    session_id=None,
    user_id=None,
):
    query = payload[-1].content if payload else None
    with start_agent_trace(
        session_id=session_id,
        user_id=user_id,
        tags=["agent", "langgraph", "groq"],
        query=query,
    ) as trace:
        callbacks = [JsonLlmLogger()]
        if trace["handler"] is not None:
            callbacks.insert(0, trace["handler"])
        result = llm.invoke(
            {"messages": payload},  # type: ignore
            config={"recursion_limit": 15, "callbacks": callbacks},  # type: ignore
        )  # type: ignore
        if trace["span"] is not None:
            last = result["messages"][-1]
            output = last.content if hasattr(last, "content") else str(last)
            trace["span"].update(output={"response": output})
        return result


@celery_app.task(name="agent", bind=True, max_retries=3, default_retry_delay=1)
def agent(self, query: str):
    try:
        message = [HumanMessage(query)]
        if message is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be None"
            )
        try:
            result = run_agent_safely(message, session_id=self.request.id)
            output = [
                pprint.pformat(output.content, indent=2, width=40)
                for output in reversed(result["messages"])
                if getattr(output, "type", None) == "ai"
            ]
            return output

        except GraphRecursionError:
            result = Finetuned.predict(user_text=query, api_name="/predict")
            return result

    except Exception as e:  # noqa: BLE001
        error = str(e).lower()
        if " temporarily at capacity" in error or "503" in error:
            try:
                raise self.retry(exc=e, countdown=15 * (self.request.retries + 1))
            except MaxRetriesExceededError:
                pass
        dlq = {
            "prompt": query,
            "time": time.time(),
            "error": str(e),
        }
        client.rpush("dlq:agent", json.dumps(dlq))
        return {"status": "failed", "moved_to_dlq": True, "error": str(e)}
