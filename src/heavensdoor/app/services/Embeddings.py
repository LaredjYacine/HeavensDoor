from typing import Any

from fastembed import TextEmbedding
from supabase import create_client

from .credentials import supabase_key, supabase_url

assert supabase_url is not None
assert supabase_key is not None


supabase_client = create_client(supabase_url, supabase_key)
dataset = supabase_client.table("Jobs").select("job_description,id").execute()
embedding_model = TextEmbedding("BAAI/bge-small-en-v1.5")
for row in dataset.data:
    item: dict[str, Any] = row  # type: ignore
    embedding = next(iter(embedding_model.embed([item["job_description"]])))
    supabase_client.table("Jobs").update({"embeddings": embedding.tolist()}).eq(
        "id", item["id"]
    ).execute()
    print("updated with success")
