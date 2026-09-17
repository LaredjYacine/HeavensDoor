import httpx
from gradio_client import Client
from ..services.credentials import hf_token
import requests
import ssl
import certifi

import os
os.environ["SSL_CERT_FILE"] = certifi.where()

Finetuned = Client("LynixSakara/Job_Finder_Model", token=hf_token)
