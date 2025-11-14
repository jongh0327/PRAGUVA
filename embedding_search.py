# entry_node_search.py
from typing import Any, Dict, List
from neo4j import Driver
from sentence_transformers import SentenceTransformer
import config


def build_embedding_model() -> SentenceTransformer:
    """
    Build the SentenceTransformer model defined in config.EMBEDDING_MODEL.
    """
    model_name = getattr(config, "EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    return SentenceTransformer(model_name)


def hybrid_search(
    driver: Driver,
    embedding_model: SentenceTransformer,
    query_text: str,
    alpha: float = 0.5,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search combining text-based and graph-based embeddings.
    alpha ∈ [0, 1]: weight given to text vs graph embeddings.
    """
    user_embedding = embedding_model.encode(query_text).tolist()
    search_k = max(100, top_k * 5)

    cypher = """
    // ---- Text-based vector search ----
    CALL db.index.vector.queryNodes('searchable_feature_index', $search_k, $user_embedding)
    YIELD node AS tNode, score AS tScore
    RETURN elementId(tNode) AS tNodeEid, tNode, tScore
    """

    cypher_graph = """
    // ---- Graph-based vector search ----
    CALL db.index.vector.queryNodes('searchable_graphSage_index', $search_k, $user_embedding)
    YIELD node AS gNode, score AS gScore
    RETURN elementId(gNode) AS gNodeEid, gNode, gScore
    """

    combine_query = f"""
    // Run text-based vector search
    CALL () {{
        {cypher}
    }}
    WITH collect({{eid: tNodeEid, node: tNode, score: tScore}}) AS textResults

    // Run graph-based vector search
    CALL () {{
        {cypher_graph}
    }}
    WITH textResults, collect({{eid: gNodeEid, node: gNode, score: gScore}}) AS graphResults

    // Combine by node ID
    UNWIND textResults AS t
    UNWIND graphResults AS g
    WITH t, g
    WHERE t.eid = g.eid
    WITH
        coalesce(t.node, g.node) AS node,
        coalesce(t.eid, g.eid) AS nodeEid,
        coalesce(t.score, 0.0) AS tScore,
        coalesce(g.score, 0.0) AS gScore
    WHERE NOT 'Topic' IN labels(node)
    WITH node, nodeEid,
        ($alpha * tScore + (1 - $alpha) * gScore) AS combinedScore,
        tScore, gScore
    RETURN node, nodeEid, labels(node) AS nodeLabels, tScore, gScore, combinedScore
    ORDER BY combinedScore DESC
    LIMIT $top_k
    """

    try:
        with driver.session() as session:
            result = session.run(
                combine_query,
                user_embedding=user_embedding,
                alpha=alpha,
                top_k=top_k,
                search_k=search_k,
            )
            data = result.data()

            # Debug output preserved from original script
            print("\n[DEBUG] Hybrid search details:")
            for r in data:
                labels = r.get("nodeLabels", [])
                t_score = r.get("tScore", 0.0)
                g_score = r.get("gScore", 0.0)
                combined = r.get("combinedScore", 0.0)

                print(f"Labels: {labels}")
                print(f"  Text Score:  {t_score:.4f}")
                print(f"  Graph Score: {g_score:.4f}")
                print(f"  Combined:    {combined:.4f}\n")

            return data
    except Exception as e:
        print(f"Hybrid search error: {e}")
        return []


def search_by_embedding(
    driver: Driver,
    embedding_model: SentenceTransformer,
    query_text: str,
    index_name: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Simple vector search against a single Neo4j vector index.
    """
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
                user_embedding=user_embedding,
            )
            return result.data()
    except Exception as e:
        print(f"Vector search error: {e}")
        return []


def search_professors_and_courses(
    driver: Driver,
    embedding_model: SentenceTransformer,
    query_text: str,
    top_k: int = 3,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convenience helper that searches professor and course indices.
    """
    professors = search_by_embedding(
        driver, embedding_model, query_text, "professor_embeddings", top_k
    )
    courses = search_by_embedding(
        driver, embedding_model, query_text, "course_embeddings", top_k
    )
    return {"professors": professors, "courses": courses}