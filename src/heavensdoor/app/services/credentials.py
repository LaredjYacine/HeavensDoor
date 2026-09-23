import os

import dotenv
from supabase import create_client

dotenv.load_dotenv()
hf_token: str | None = os.getenv("hf_token")
supabase_url: str | None = os.getenv("supabase_url")
supabase_key: str | None = os.getenv("supabase_Key")
service_role: str | None = os.getenv("service_role")
if supabase_key is None or supabase_url is None:
    raise ValueError("Supabase Credentials must not be None")

redisurl = os.getenv("redisurl")
supabase_client = create_client(supabase_url, supabase_key)
groq_api_key = os.getenv("groq")
if groq_api_key is None:
    raise ValueError("groq_api_key is not set")
if "GROQ_API_KEY" not in os.environ:
    os.environ["GROQ_API_KEY"] = groq_api_key
