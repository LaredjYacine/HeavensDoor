from langchain_groq import ChatGroq

evaluation_model = ChatGroq(model="meta-llama/llama-prompt-guard-2-86m")


def evaluate_response(response_text: str):

    result = evaluation_model.invoke(response_text)
    return result.content
