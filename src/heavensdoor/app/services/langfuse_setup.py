import contextlib
import os

import dotenv

dotenv.load_dotenv()

LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
)


@contextlib.contextmanager
def start_agent_trace(
    *,
    name="job-matching-agent",
    session_id=None,
    user_id=None,
    tags=None,
    query=None,
):
    """Context manager that wraps one LangGraph run in a Langfuse trace.

    Yields a dict with two keys:
        "handler": the LangChain CallbackHandler to add to the run callbacks,
                   or None when Langfuse is not configured.
        "span":    the root span of the trace, or None when Langfuse is not
                   configured. Call "span".update(output=...) with the final
                   result to capture the trace output.

    Trace-level attributes (trace name, session id, tags) are propagated to
    every LLM/generation/tool observation created by the LangChain handler.
    """
    if not LANGFUSE_ENABLED:
        yield {"handler": None, "span": None}
        return

    from langfuse import get_client, propagate_attributes
    from langfuse.langchain import CallbackHandler

    langfuse = get_client()

    with (
        langfuse.start_as_current_observation(
            as_type="span", name="agent-execution", input={"query": query}
        ) as span,
        propagate_attributes(
            trace_name=name,
            session_id=session_id,
            user_id=user_id,
            tags=tags,
        ),
    ):
        yield {"handler": CallbackHandler(), "span": span}
