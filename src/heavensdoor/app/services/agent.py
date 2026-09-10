
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

model = HuggingFaceEndpoint(
    endpoint_url="",
    huggingfacehub_api_token="",
    temprature=0.7
)

chat_model = ChatHugginFace(llm=model)
