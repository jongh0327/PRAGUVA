# entry_node_search.py
from typing import Any, Dict, List, Optional
from neo4j import Driver
from sentence_transformers import SentenceTransformer
import config


def build_embedding_model() -> SentenceTransformer:
    """
    Build the SentenceTransformer model defined in config.EMBEDDING_MODEL.
    """
    model_name = getattr(config, "EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    return SentenceTransformer(model_name)

def search_by_embedding(
    driver: Driver,
    embedding_model: SentenceTransformer,
    query_text: str,
    top_k: int = 5,
    search_k: Optional[int] = None,
    whitelist: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Vector search with optional label whitelist.
    Larger search_k ensures enough candidates survive filtering.
    """
    user_embedding = embedding_model.encode(query_text).tolist()

    if search_k is None:
        search_k = max(top_k * 5, 100)

    where_clause = ""
    if whitelist:
        where_clause = "WHERE NONE(lbl IN labels(node) WHERE lbl IN ['Topic','Paper'])"

    cypher = f"""
    CALL db.index.vector.queryNodes('searchable_feature_index', $search_k, $user_embedding)
    YIELD node, score
    {where_clause}
    RETURN node, elementId(node) AS nodeEid, score
    ORDER BY score DESC
    LIMIT $top_k
    """

    try:
        with driver.session() as session:
            result = session.run(
                cypher,
                search_k=search_k,
                top_k=top_k,
                user_embedding=user_embedding,
                whitelist=whitelist,
            )
            return result.data()
    except Exception as e:
        print(f"Vector search error: {e}")
        return []


def search_entry_nodes(
    driver: Driver,
    embedding_model: SentenceTransformer,
    query_text: str,
    top_k: int = 5,
    whitelist: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:

    # Dynamically compute default whitelist
    if whitelist is None:
        with driver.session() as session:
            labels = session.run("""
                CALL db.labels() YIELD label
                RETURN collect(label) AS labels
            """).single()["labels"]

        # Exclude Topic and Paper
        whitelist = [lbl for lbl in labels if lbl not in ("Topic", "Paper")]

    return search_by_embedding(
        driver,
        embedding_model,
        query_text,
        top_k=top_k,
        whitelist=whitelist,
    )