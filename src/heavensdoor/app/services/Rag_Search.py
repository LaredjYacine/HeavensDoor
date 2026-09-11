from .credentials import supabase_client
from fastembed import TextEmbedding
def rag_function(query_vector:str):
    embedded_query = list(TextEmbedding().embed([query_vector]))[0]
    vector_threshold=0.75
    match_count = 5
    dataset = supabase_client.rpc('cosine_similarity',{'query_vector':embedded_query.tolist() ,'vector_threshold': vector_threshold, 'match_count': match_count, }).execute()
    for data in dataset.data :
        print(data['id'])



rag_function('Software Engineer')
