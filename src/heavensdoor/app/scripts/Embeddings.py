from typing import Any

from ..services.credentials import supabase_client
from ..services.embedmodel import get_embedding_model

embedding_model = get_embedding_model()
dataset = (
    supabase_client.table("Jobs")
    .select("job_description,id")
    .is_("embeddings", "null")
    .execute()
)
# dataset = supabase_client.table("Jobs").select("job_description,id").execute()
if dataset.data:
    for row in dataset.data:
        item: dict[str, Any] = row  # type: ignore
        embedding = next(iter(embedding_model.embed([item["job_description"]])))
        supabase_client.table("Jobs").update({"embeddings": embedding.tolist()}).eq(
            "id", item["id"]
        ).execute()
        print("updated with success")
