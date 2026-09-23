import time
import uuid

from langchain_core.callbacks import BaseCallbackHandler


def LogSchema(step_type, node_name, data):
    entry = {
        "step_type": step_type,
        "time": time.time(),
        "node_name": node_name,
        "data": data,
        "id": str(uuid.uuid4()),
    }
    with open("agent_trace.jsonl", "a") as f:
        f.write(str(entry))


class JsonLlmLogger(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        LogSchema("llm_start", "llm", {"prompt": str(prompts)})

    def on_llm_end(self, response, **kwargs):
        LogSchema("llm_end", "llm", {"response": str(response)})

    def on_tool_start(self, serialized, input_str, **kwargs):
        LogSchema("on_tool_start", serialized.get("name"), {"input": str(input)})

    def on_tool_end(self, output, **kwargs):
        LogSchema("on_tool_end", "tool", {"output": str(output)})
