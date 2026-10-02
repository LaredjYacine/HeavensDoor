from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .agent_models import MessageState, llm_calls, should_continue, tool_node

memory = MemorySaver()
agent_builder = StateGraph(MessageState)
agent_builder.add_node("llm_calls", llm_calls)  # type: ignore
agent_builder.add_node("tool_node", tool_node)  # type: ignore

agent_builder.add_edge(START, "llm_calls")
agent_builder.add_conditional_edges("llm_calls", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "llm_calls")
llm = agent_builder.compile(checkpointer=memory)

# fall back Model
agent_builder_fallback = StateGraph(MessageState)
agent_builder_fallback.add_node("llm_calls", llm_calls)  # type: ignore
agent_builder_fallback.add_node("tool_node", tool_node)  # type: ignore
agent_builder_fallback.add_edge(START, "llm_calls")
agent_builder_fallback.add_conditional_edges(
    "llm_calls", should_continue, ["tool_node", END]
)
agent_builder_fallback.add_edge("tool_node", "llm_calls")
fallback_model = agent_builder_fallback.compile(checkpointer=memory)
