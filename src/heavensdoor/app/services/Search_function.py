from typing import Any

from fastembed import TextEmbedding

from .credentials import supabase_client


def rag_function(query_vector: str) -> list[Any]:
    embedded_query = next(
        iter(TextEmbedding(model="BAAI/bge-small-en-v1.5").embed([query_vector]))
    )

    vector_threshold = 0.50
    match_count = 2
    dataset = supabase_client.rpc(
        "cosine_similarity",
        {
            "query_vector": embedded_query.tolist(),
            "vector_threshold": vector_threshold,
            "match_count": match_count,
        },
    ).execute()
    if not isinstance(dataset.data, list):
        raise TypeError(f"Expected dataset.data to be a list got {type(dataset.data)}")
    result: list = dataset.data
    return result


def bm25_function(query_vector: str) -> list[Any]:
    match_count = 1
    data = supabase_client.rpc(
        "search_jobs_fts", {"search_query": query_vector, "match_limit": match_count}
    ).execute()
    if not isinstance(data.data, list):
        raise TypeError(f"Expected data.data to be a list got {type(data.data)}")
    return data.data


def hybridSearch(query: str) -> list[dict[str, Any]]:
    # comment :   A main problem in this hybrid search is  the lack of a ranker So
    # i will only fetch little information for now But when ranker is avaialble
    # fetch only the top 5
    rag_results: list = rag_function(query)
    bm25_results: list = bm25_function(query)
    hybridsearch = rag_results + bm25_results  # type: ignore
    return hybridsearch
