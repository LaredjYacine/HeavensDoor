from .credentials import supabase_url, supabase_key
from supabase import create_client
from fastembed import TextEmbedding
import numpy as np
from typing import Dict, Any
assert supabase_url is not None
assert supabase_key is not None


supabase_client = create_client(supabase_url, supabase_key)
dataset= supabase_client.table('Jobs').select('job_description,id').execute()
embedding_model = TextEmbedding('BAAI/bge-small-en-v1.5')
for row in dataset.data :
    item: Dict[str, Any] = row # type: ignore
    embedding = list((embedding_model.embed([item['job_description']])))[0]
    supabase_client.table('Jobs').update({'embeddings': embedding.tolist()}).eq('id', item['id']).execute()
    print('updated with success')
