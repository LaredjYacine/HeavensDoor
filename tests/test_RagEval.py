import os

import dotenv
import pytest
from deepeval import evaluate
from deepeval.dataset import EvaluationDataset
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase
from langchain.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from openai import OpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from heavensdoor.app.services.Search_function import hybridSearch

dotenv.load_dotenv()
dataset = EvaluationDataset()
dataset.add_goldens_from_json_file("tests/GoldenTestCase.json")  # bare array


class GroqDeepEvalModel(DeepEvalBaseLLM):
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)

    def load_model(self):  # type: ignore
        return self.client

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True,
    )
    def generate(self, prompt: str) -> str:
        client = self.load_model()
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        if response.choices[0].message.content:
            return response.choices[0].message.content[:12000]
        return ""

    async def a_generate(self, prompt: str) -> str:
        # For async evaluation runs\
        return self.generate(prompt)

    def get_model_name(self):
        return self.model_name


def llm_response(context: str, query: str) -> str:
    messages = [
        SystemMessage(
            content=(
                "You are a helpful assistant. "
                "Answer the user's question naturally and directly. "
                "DO NOT use phrases like 'Based on the context', 'According to the text', 'As shown in the context', or 'The context says'. "
                "Just speak naturally as if you already know the information."
                f"Here is what you know:\n{context}\n\n"
            )
        ),
        HumanMessage(content=(f"Question: {query}")),
    ]

    chat_model = ChatGroq(
        model="qwen/qwen3.8-27b",
        temperature=0.7,
    )

    response = chat_model.invoke(messages)
    return str(response.content)


@pytest.mark.parametrize("golden", dataset.goldens[:3])
def test_evaluation(golden, monkeypatch):
    docs = hybridSearch(golden.input)
    context = [
        str(doc.get("content"))
        for doc in docs
        if isinstance(doc, dict) and doc.get("content") is not None
    ]
    text = "|".join(context)
    if len(text) > 7500:
        text = text[:7500]
    substitute_key = os.getenv("Test_Key")
    if not substitute_key:
        return "Test key is not Set"
    monkeypatch.setenv("GROQ_API_KEY", substitute_key)
    output = llm_response(text, golden.input)
    test_case = LLMTestCase(
        input=golden.input,
        actual_output=output,
        expected_output=golden.expected_output,
        retrieval_context=context,  # type: ignore
    )
    model = GroqDeepEvalModel(model_name="qwen/qwen3.8-27b", api_key=substitute_key)
    metrics = [
        FaithfulnessMetric(threshold=0.7, model=model),
        AnswerRelevancyMetric(threshold=0.7, model=model),
    ]
    evaluate(
        test_cases=[test_case],
        metrics=metrics,
        # async_config=AsyncConfig(
        #     run_async=True,
        #     max_concurrent=1,
        #     throttle_value=3
        # ),
    )
