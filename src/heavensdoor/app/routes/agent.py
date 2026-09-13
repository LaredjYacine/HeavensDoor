from fastapi import APIRouter, HTTPException, status
from ..services.limiter import limiter
from fastapi.requests import Request
from ..services.agent import llm
from langchain.messages import HumanMessage
from langgraph.errors import GraphRecursionError

route = APIRouter()


@route.get('/agent')
@limiter.limit("5/minute")
def agent(request: Request, query:str):
    message = [HumanMessage(query)]
    if message is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='query must not be None')
    try :
        result = llm.invoke({"messages":message}, config={'recursion_limit':15 })
    except GraphRecursionError:
        return 'placeholder error'
