import os

import certifi
from gradio_client import Client

from ..services.credentials import hf_token

os.environ["SSL_CERT_FILE"] = certifi.where()
def get_fineTuneModel():
    try:
        Finetuned = Client("LynixSakara/Job_Finder_Model", token=hf_token)
        return Finetuned
    except Exception as e:
        return None


Finetuned = get_fineTuneModel()
