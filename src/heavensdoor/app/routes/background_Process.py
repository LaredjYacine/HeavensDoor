import json
import pprint
import time

import httpx
from celery.exceptions import MaxRetriesExceededError
from fastapi import HTTPException, status
from groq import RateLimitError
from huggingface_hub.errors import BadRequestError, HfHubHTTPError
from langchain.messages import HumanMessage
from langgraph.errors import GraphRecursionError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from upstash_redis import Redis

from ..services.agent import fallback_model, llm
from ..services.celery import celery_app
from ..services.langfuse_setup import start_agent_trace
from ..services.Logger import JsonLlmLogger
from ..services.SSL_fix import Finetuned

client = Redis.from_env()


class FallbackModelUnavailableError(RuntimeError):
    """The hosted fine-tuned fallback model could not be reached or loaded."""


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
    llm,
    session_id=None,
    user_id=None,
    user_session_id=None,
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
            config={
                "configurable": {"thread_id": user_session_id},
                "recursion_limit": 15,
                "callbacks": callbacks,
            },  # type: ignore
        )  # type: ignore

        if trace["span"] is not None:
            last = result["messages"][-1]
            output = last.content if hasattr(last, "content") else str(last)
            trace["span"].update(output={"response": output})
        return result


@celery_app.task(name="agent", bind=True, max_retries=3, default_retry_delay=1)
def agent(self, session_id: str, query: str):
    try:
        if query is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be None"
            )
        message = [HumanMessage(query)]
        try:
            result = run_agent_safely(message, llm, session_id=self.request.id)
            output = [
                pprint.pformat(output.content, indent=2, width=40)
                for output in reversed(result["messages"])
                if getattr(output, "type", None) == "ai"
            ]
            return output
        except RateLimitError:
            try:
                result = run_agent_safely(
                    message, fallback_model, session_id=self.request.id
                )
                output = [
                    pprint.pformat(output.content, indent=2, width=40)
                    for output in reversed(result["messages"])
                    if getattr(output, "type", None) == "ai"
                ]
                return output
            except Exception as e:  # noqa: BLE001 If the Secondary Model prints back an error we Catch it and raise it to the outer layer
                raise FallbackModelUnavailableError(
                    {
                        "Hugging Face fall back model (not the Fined tuned one ) error": str(
                            e
                        )
                    }
                )

        except GraphRecursionError:
            try:
                if Finetuned is None:
                    raise FallbackModelUnavailableError(
                        "Failed to get fine-tuned model"
                    )
                return Finetuned.predict(user_text=query, api_name="/predict")
            except (
                FallbackModelUnavailableError,
                httpx.HTTPError,
                HfHubHTTPError,
            ) as e:
                return str(e)

    except Exception as e:  # noqa: BLE001 - process boundary: convert any failure into a DLQ recor
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
