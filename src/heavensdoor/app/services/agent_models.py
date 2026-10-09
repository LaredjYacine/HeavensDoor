import operator
from typing import Annotated, Literal, TypedDict

import truststore
from langchain.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.graph import END

from .credentials import hf_token
from .tools import tools

truststore.inject_into_ssl()
if hf_token is None:
    raise ValueError("hf_token is not set")


model = ChatGroq(model="meta-llama/llama-prompt-guard-2-22m")  # type: ignore


chat_model = ChatGroq(model="qwen/qwen3.8-27b", temperature=0.7)

chat_model_Fall_Back = model  # ChatGroq(llm=model)


tools_by_name = {tool.name: tool for tool in tools}
model_with_tools = chat_model.bind_tools(tools)
fallback_model_with_tools = chat_model_Fall_Back.bind_tools(tools)


class MessageState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


def llm_calls(state: dict):
    """
    LLM decides whether to call a tool or not


    """
    return {
        "messages": [
            model_with_tools.invoke(
                [
                    SystemMessage(
                        content=(
                            """ you are an assistant your task is to Help the user To either find a candidate or a job,
                            Your must give a General summary to  the output to fit the users request
                             """
                        )
                    )
                ]
                + state["messages"]
            )
        ],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def llm_calls_FallBack(state: dict):
    """
    LLM decides whether to call a tool or not


    """
    return {
        "messages": [
            fallback_model_with_tools.invoke(
                [
                    SystemMessage(
                        content=(
                            """ you are an assistant your task is to Help the user To either find a candidate or a job,
                            Your must give a General summary to  the output to fit the users request
                             """
                        )
                    )
                ]
                + state["messages"]
            )
        ],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def make_llm_node(model_to_use):
    def node_func(state: dict):
        return {
            "messages": [
                model_to_use.invoke(
                    [
                        SystemMessage(
                            content=(
                                "you are an assistant your task is to Help the user To either find a candidate or a job, "
                                "Your must give a General summary to the output to fit the users request"
                            )
                        )
                    ]
                    + state["messages"]
                )
            ],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

    return node_func


def should_continue(state: dict) -> Literal["tool_node", END]:  # type: ignore
    """Decide if the we  should continue or not based on wethere if the LLm called a  tool"""
    messages = state["messages"]
    call = messages[-1]
    if call.tool_calls:
        return "tool_node"
    return END


def tool_node(state: dict):
    """perform tool calls"""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}
