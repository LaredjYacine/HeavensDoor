
from langchain_ollama import OllamaLLM


model = OllamaLLM(
    model="qwen2.5:14b",
    base_url='http://localhost:11434',
)
