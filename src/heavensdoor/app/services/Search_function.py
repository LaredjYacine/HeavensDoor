from typing import Any

from .credentials import supabase_client
from .embedmodel import get_embedding_model

embedding_model = get_embedding_model()


def rrf(lists, k=10):
    scores = {}
    for lst in lists:
        for rank, row in enumerate(lst, start=1):
            rid = row["id"]
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def rag_function(query_vector: str) -> list[Any]:
    embedded_query = next(iter(embedding_model.embed([query_vector])))

    vector_threshold = 0.50
    match_count = 10
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
    match_count = 10
    data = supabase_client.rpc(
        "search_jobs_fts", {"search_query": query_vector, "match_limit": match_count}
    ).execute()
    if not isinstance(data.data, list):
        raise TypeError(f"Expected data.data to be a list got {type(data.data)}")
    return data.data


def hybridSearch(query: str) -> list[Any] | None:
    # comment :   A main problem in this hybrid search is  the lack of a ranker So
    # i will only fetch little information for now But when ranker is avaialble
    # fetch only the top 5
    rag_results: list = rag_function(query)
    bm25_results: list = bm25_function(query)
    rag_sorted = sorted(rag_results, key=lambda r: r["similarity"], reverse=True)
    bm25_sorted = sorted(bm25_results, key=lambda r: r["score"], reverse=True)
    fused_ids = [rid for rid, _ in rrf([rag_sorted, bm25_sorted])]

    if not fused_ids:
        return []

    data = supabase_client.table("Jobs").select("*").in_("id", fused_ids).execute()
    rows = data.data if data.data else None
    return rows
