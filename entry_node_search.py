from typing import Dict, Any, List
from neo4j import GraphDatabase, Driver
from sentence_transformers import SentenceTransformer
import config

def build_embedding_model() -> SentenceTransformer:
    model_name = getattr(config, "EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    return SentenceTransformer(model_name)

def _search_by_embedding(
    driver: Driver,
    embedding_model: SentenceTransformer,
    query_text: str,
    index_name: str,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    user_embedding = embedding_model.encode(query_text).tolist()

    cypher = """
    CALL db.index.vector.queryNodes($index_name, $top_k, $user_embedding)
    YIELD node, score
    RETURN node, elementId(node) AS nodeEid, score
    ORDER BY score DESC
    """

    try:
        with driver.session() as session:
            result = session.run(
                cypher,
                index_name=index_name,
                top_k=top_k,
                user_embedding=user_embedding
            )
            return result.data()
    except Exception as e:
        print(f"Vector search error ({index_name}): {e}")
        return []

def search_professors_and_courses(
    driver: Driver,
    embedding_model: SentenceTransformer,
    query_text: str,
    top_k: int = 3
) -> Dict[str, List[Dict[str, Any]]]:
    professors = _search_by_embedding(driver, embedding_model, query_text, "professor_embeddings", top_k)
    courses = _search_by_embedding(driver, embedding_model, query_text, "course_embeddings", top_k)
    return {"professors": professors, "courses": courses}
