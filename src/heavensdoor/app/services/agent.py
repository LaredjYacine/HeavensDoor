from .agent_models import llm_calls , should_continue , tool_node, MessageState
from langgraph.graph import StateGraph, END , START

agent_builder = StateGraph(MessageState)
agent_builder.add_node("llm_calls",llm_calls)#type: ignore
agent_builder.add_node("tool_node",tool_node)#type: ignore

agent_builder.add_edge(START, "llm_calls")
agent_builder.add_conditional_edges(
    "llm_calls"
    ,should_continue,
    ["tool_node",END]
)
agent_builder.add_edge("tool_node","llm_calls")
agent = agent_builder.compile()
