from ..services.celery import celery_app
from ..services.credentials import redisurl
from fastapi import APIRouter, HTTPException, status
from ..services.limiter import limiter
from fastapi.requests import Request
from ..services.agent import llm
from langchain.messages import HumanMessage
from langgraph.errors import GraphRecursionError
from ..services.Logger import JsonLlmLogger
from fastapi.sse import EventSourceResponse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from huggingface_hub.errors import BadRequestError
import httpx
import pprint
import time
import json
from celery.exceptions import MaxRetriesExceededError
from upstash_redis import Redis
import certifi
from gradio_client import Client
from ..services.credentials import hf_token
from ..services.SSL_fix import Finetuned


client = Redis.from_env()


def streaming(messages):
    for chunk in messages :
        if chunk.get('type') == "messages":
            message , metadata = chunk['data']
            yield message.content

@retry(
    stop=stop_after_attempt(4),  # Try up to 4 times
    wait=wait_exponential(multiplier=2, min=2, max=10),  # Wait 2s, 4s, 8s... between tries
    retry=retry_if_exception_type((BadRequestError, httpx.HTTPStatusError, Exception)),
    reraise=True  # Raise the final error if all retries fail
)
def run_agent_safely( payload, ):
    return llm.invoke({"messages":payload} , config={'recursion_limit':15  , 'callbacks':[JsonLlmLogger()]})#type: ignore


@celery_app.task(name='agent',  bind=True , max_retries=3,default_retry_delay=1)
def agent(self ,query:str):
    try:
        message = [HumanMessage(query)]
        if message is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='query must not be None')
        try :
            result = run_agent_safely(message)
            output=[pprint.pformat(output.content, indent=2, width=40) for output in reversed(result['messages']) if getattr(output,'type', None)=='ai']
            return output

        except GraphRecursionError:
            result = Finetuned.predict(user_text=query, api_name="/predict")
            return result



    except Exception as e:
        error=  str(e).lower()
        if " temporarily at capacity"  in error or "503" in error :
            try:
                raise self.retry(exc=e, countdown=15 * (self.request.retries + 1))
            except MaxRetriesExceededError:
                pass
        dlq={
            'prompt':query,
            'time': time.time(),
            'error':str(e),


        }
        client.rpush("dlq:agent", json.dumps(dlq))
        return {"status": "failed", "moved_to_dlq": True, "error": str(e)}
