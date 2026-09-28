import os

import certifi
import httpx
from gradio_client import Client
from huggingface_hub.errors import HfHubHTTPError

from ..services.credentials import hf_token

os.environ["SSL_CERT_FILE"] = certifi.where()


# to
def get_fineTuneModel():
    """Return the hosted fallback client, or None when it cannot be loaded.

    The fine-tuned model is an optional secondary path, so a failure here must
    never stop the app from starting: every anticipated failure is mapped to
    None and handled by the caller instead.
    """
    try:
        return Client("LynixSakara/Job_Finder_Model", token=hf_token)
    except (ValueError, HfHubHTTPError, httpx.HTTPError):
        return None


Finetuned = get_fineTuneModel()
