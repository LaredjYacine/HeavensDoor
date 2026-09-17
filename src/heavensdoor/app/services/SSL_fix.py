import httpx
from huggingface_hub import configure_http_backend
from gradio_client import Client
from ..services.credentials import hf_token
import requests
import ssl
import certifi
def backend_factory() -> httpx.Client:
    # Dev/quick fix — skips verification entirely:
    return httpx.Client(verify=False)

    # Proper fix — verify against a specific CA bundle instead:
    # return httpx.Client(verify=certifi.where())

configure_http_backend(backend_factory=backend_factory)

# Only AFTER this line:
Finetuned = Client("LynixSakara/Job_Finder_Model", token=hf_token)
