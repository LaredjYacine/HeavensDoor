from .credentials import supabase_client
from fastembed import TextEmbedding
import json
def rag_function(query_vector:str):
    embedded_query = list(TextEmbedding(model =  "BAAI/bge-small-en-v1.5").embed([query_vector]))[0]
    vector_threshold=0.50
    match_count = 5
    dataset = supabase_client.rpc('cosine_similarity',{'query_vector':embedded_query.tolist() ,'vector_threshold': vector_threshold, 'match_count': match_count, }).execute()
    return dataset.data





def bm25_function(query_vector:str):
    match_count=5
    data = supabase_client.rpc('search_jobs_fts',{'search_query':query_vector , 'match_limit':match_count}).execute()
    return data.data





def hybridSearch(query:str):
    rag_results   = rag_function(query)
    bm25_results = bm25_function(query)
    hybridsearch = rag_results + bm25_results #type: ignore
    return hybridsearch
