import json
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
    with open("agent_trace.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, indent=2) + "\n")


class JsonLlmLogger(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        LogSchema("llm_start", "llm", {"prompt": prompts})

    def on_llm_end(self, response, **kwargs):

        LogSchema("llm_end", "llm", {"response": response.generations[0][0].text})

    def on_tool_start(self, serialized, input_str, **kwargs):
        LogSchema("on_tool_start", serialized.get("name"), {"input": input_str})

    def on_tool_end(self, output, **kwargs):
        LogSchema("on_tool_end", "tool", {"output": output})
