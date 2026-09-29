import os

import dotenv
import pytest
from deepeval.dataset import EvaluationDataset
from deepeval.test_case import LLMTestCase
from langchain_groq import ChatGroq

from ..src.heavensdoor.app.services.Search_function import hybridSearch

dotenv.load_dotenv()
dataset = EvaluationDataset()
dataset.add_goldens_from_json_file("tests/GoldenTestCase.json")  # bare array


def llm_response(context, query):
    chat_model = ChatGroq(
        model="qwen/qwen3.8-27b",
        temperature=0.7,
        system_prompt=(
            "Answer the question using ONLY the information in the context below. "
            "If the context doesn't contain the answer, say 'I don't know based on the given context.'"
        ),
    )
    response = chat_model.invoke(f"Context: {context}\n\nQuestion: {query}")
    return response.content


@pytest.mark.parametrize("golden", dataset.goldens)
def test_evaluation(golden, monkeypatch):
    docs = hybridSearch(golden.input)
    context = [doc["content"] for doc in docs]
    substitute_key = os.getenv("Test_Key")
    monkeypatch.setenv("GROQ_API_KEY", substitute_key)
    output = llm_response(context, golden.input)
    test_case = LLMTestCase(
        input=golden.input,
        actual_output=output,
        expected_output=golden.expected_output,
        retrieval_context=context,
    )
    print(test_case)
