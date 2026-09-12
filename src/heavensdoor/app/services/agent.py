
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from .credentials import hf_token
import truststore
truststore.inject_into_ssl()
if hf_token is None:
   raise ValueError("hf_token is not set")



model= HuggingFaceEndpoint(
    repo_id="LynixSakara/Hopefully_Not_Overfitted",
    task="text-generation",
    do_sample=False,
    huggingfacehub_api_token=hf_token,
)# type: ignore

response = model.invoke("my skills are python and i need a job")
print(response)
