from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from .agent_models import MessageState, llm_calls, should_continue, tool_node

memory = MemorySaver()
agent_builder = StateGraph(MessageState)
agent_builder.add_node("llm_calls", llm_calls)  # type: ignore
agent_builder.add_node("tool_node", tool_node)  # type: ignore

agent_builder.add_edge(START, "llm_calls")
agent_builder.add_conditional_edges("llm_calls", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "llm_calls")
llm = agent_builder.compile(checkpointer=memory)
