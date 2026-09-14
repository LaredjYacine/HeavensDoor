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



route = APIRouter()

def streaming(messages):
    for chunk in messages :
        if chunk.get('type') == "messages":
            message , metadata = chunk['data']
            yield message.content

@retry(
    stop=stop_after_attempt(4),  # Try up to 4 times
    wait=wait_exponential(multiplier=2, min=2, max=10),  # Wait 2s, 4s, 8s... between tries
    retry=retry_if_exception_type((BadRequestError, httpx.HTTPStatusError)),
    reraise=True  # Raise the final error if all retries fail
)
def run_agent_safely( payload, ):
    return llm.invoke({"messages":payload} , config={'recursion_limit':15  , 'callbacks':[JsonLlmLogger()]})#type: ignore

@route.get('/agent')
@limiter.limit("5/minute")
def agent(request: Request, query:str):#, response_class=EventSourceResponse):
    message = [HumanMessage(query)]
    if message is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='query must not be None')
    try :
        #result = llm.stream({"messages":message},version='v2', config={'recursion_limit':15  , 'callbacks':[JsonLlmLogger()]}, stream_mode="messages")#type: ignore
        #= streaming(result)
        result = run_agent_safely(message)
        output=[output for output in result['messages']]
        return output

    except GraphRecursionError:
        return 'placeholder error'
    except Exception as e:
        return str(e)
