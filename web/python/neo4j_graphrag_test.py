#!/usr/bin/env python3
import os
import json
from neo4j import GraphDatabase
import web.python.config as config
from typing import Any, Dict, List
from sentence_transformers import SentenceTransformer
import argparse

from google import genai
from google.genai import types

"""
Begin embedding similarity code
"""

def build_embedding_model():
    model_name = getattr(config, "EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    return SentenceTransformer(model_name)

def hybrid_search(driver, embedding_model, query_text, alpha=0.5, top_k=5):
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
                search_k = search_k
            )

            data = result.data()

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



def search_by_embedding(driver, embedding_model, query_text: str, index_name: str, top_k: int = 3):
    user_embedding = embedding_model.encode(query_text).tolist()

    # NOTE: return id(node) as nodeId so we can seed the 2-hop subgraph later.
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
                index_name = index_name,
                top_k = top_k,
                user_embedding = user_embedding
            )
            rows = result.data()
            return rows
    except Exception as e:
        print(f"Vector search error: {e}")
        return []

def search_professors_and_courses(driver, embedding_model, query_text: str, top_k: int = 3):
    professors = search_by_embedding(driver, embedding_model, query_text, "professor_embeddings", top_k)
    courses = search_by_embedding(driver, embedding_model, query_text, "course_embeddings", top_k)
    return {
        "professors": professors,
        "courses": courses
    }

"""
End embedding similarity code
"""

# ---------- APOC 2-HOP SUBGRAPH ----------

def fetch_two_hop_subgraph_apoc(
    driver,
    entry_node_eids: List[str],
    *,
    max_level: int = 2,
    max_nodes: int = 1000,
    max_rels: int = 2000,
    relationship_filter: str | None = None,  # e.g. "TEACHES>|MENTORS>|CO_AUTHORED>"
    label_filter: str | None = None          # e.g. "+Professor|+Course|+Department"
):
    """
    Build a 2-hop subgraph using APOC only (no fallback).
    Returns two lists: nodes and relationships, serialized as dicts:
      nodes: [{id, labels, props}]
      relationships: [{id, type, start, end, props}]
    """
    if not entry_node_eids:
        return [], []

    cypher = """
    MATCH (seed)
    WHERE elementId(seed) IN $eids

    CALL apoc.path.subgraphAll(seed, $config)
    YIELD nodes, relationships

    WITH collect(nodes) AS nlists, collect(relationships) AS rlists
    WITH
        reduce(nacc = [], l IN nlists | nacc + l) AS nflat,
        reduce(racc = [], l IN rlists | racc + l) AS rflat
    WITH
        apoc.coll.toSet(nflat)[0..$max_nodes] AS nset,
        apoc.coll.toSet(rflat)[0..$max_rels] AS rset

    RETURN
        [n IN nset | {id: elementId(n), labels: labels(n), props: properties(n)}] AS nodes,
        [r IN rset | {id: elementId(r), type: type(r), start: elementId(startNode(r)), end: elementId(endNode(r)), props: properties(r)}] AS relationships
    """

    apoc_config = {
        "maxLevel": max_level,
        # TIP: set a traversal limit if your graph is dense
        "bfs": True,
        "uniqueness": "NODE_GLOBAL",
        # Optional filters
        **({"relationshipFilter": relationship_filter} if relationship_filter else {}),
        **({"labelFilter": label_filter} if label_filter else {}),
    }

    try:
        with driver.session() as session:
            rec = session.run(
                cypher,
                eids=entry_node_eids,
                config=apoc_config,
                max_nodes=max_nodes,
                max_rels=max_rels,
            ).single()
            if not rec:
                return [], []
            return rec["nodes"], rec["relationships"]
    except Exception as e:
        print(f"APOC subgraph error: {e}")
        return [], []

# ---------- NL FROM GRAPH (nodes + relationships) ----------

def build_genai_client() -> genai.Client:
    """Create the GenAI client (new SDK)."""
    return genai.Client(api_key=config.GEMINI_API_KEY)

def generate_NL_response(client: genai.Client, q: str,
                        nodes: List[Dict[str, Any]],
                        relationships: List[Dict[str, Any]]) -> None:
    """
    NL generation that consumes a graph snapshot (nodes + relationships).
    """
    try:
        graph_payload = {"nodes": nodes, "relationships": relationships}
        graph_json = json.dumps(graph_payload, ensure_ascii=False, indent=2)

        user_prompt = config.GEMINI_USER_PROMPT.format(
            question=q,
            results=graph_json
        )

        cfg = types.GenerateContentConfig(
            system_instruction=getattr(config, "GEMINI_SYSTEM_PROMPT", "You are a helpful assistant.")
        )

        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=user_prompt,
            config=cfg,
        )
        answer = (resp.text or "").strip()
        if answer:
            print("\n--- Answer (Graph-based) ---")
            print(answer)

    except Exception as e:
        print(f"\n--- Answer (Graph-based) ---\nGEMINI ERROR: {e}")

def generate_NL_response_with_search(client: genai.Client, q: str) -> None:
    """
    Search-grounded generation using NEW SDK.
    """
    try:
        cfg = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=q,
            config=cfg,
        )
        print("\n--- Answer (Gemini + Google Search) ---")
        print(resp.text or "(no text returned)")

    except Exception as e:
        print(f"\n--- Answer (Gemini + Google Search) ---\nGEMINI ERROR: {e}")

def main():
    #For Test Options(Comparing with Raw Gemini Output)
    parser = argparse.ArgumentParser(description="Neo4j + Gemini assistant")
    parser.add_argument("-t", "--test", action="store_true", help="Run both Gemini models (GraphRAG and Search-based)")
    parser.add_argument("--alpha", type=float, default=0.5, help="Weight for text vs. graph embeddings (0=graph only, 1=text only)")
    parser.add_argument("--top_k", type=int, default=5, help="Number of top results to return")
    args = parser.parse_args()

    # Connect to Neo4j
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )

    # Build embedding model and Gemini for NL generation
    embedding_model = build_embedding_model()
    client = build_genai_client()

    print("Embedding-based search for for All Nodes (Professors, Courses, Papers, etc.)")
    print(f"Embedding Model: {getattr(config, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}")
    print(f"NL Generation (Gemini): {config.GEMINI_MODEL}")
    print(f"Alpha (text weight): {args.alpha}")
    if args.test:
        print("Test mode: Comparing GraphRAG-style NL vs. Search-grounded NL")

    while True:
        try:
            q = input("\nQ> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit", ":q"}:
            break

        # Search both professor and course embeddings
        results = hybrid_search(driver, embedding_model, q, alpha=args.alpha, top_k=args.top_k)
        print(f"[DEBUG] main(): received {len(results)} results from hybrid_search()")

        if not results:
            print("(no results)")
            continue
        
        # Display results
        print("\n--- Top Matching Nodes (Hybrid Ranked) ---")
        for i, row in enumerate(results, 1):
            node = row["node"]
            score = row["combinedScore"]
            node_id = row["nodeEid"]

            # Extract clean properties
            if hasattr(node, "_properties"):
                props = {k: v for k, v in dict(node._properties).items() if (not k.endswith("Embedding") and not k.endswith("Vector"))}
            else:
                props = {k: v for k, v in dict(node).items() if (not k.endswith("Embedding") and not k.endswith("Vector"))}

            # Print nicely
            label = list(node.labels)[0] if hasattr(node, "labels") else "Node"
            print(f"{i}. [{label}] [Score: {score:.4f}] [id={node_id}]")
            for key, value in props.items():
                print(f"   {key}: {value}")
            print()

        # Collect Entry seed IDs
        nodes = [dict(node._properties) if hasattr(node, "_properties") else dict(node) for node in [r["node"] for r in results]]

        # ✅ Generate the natural language response using just these nodes
        generate_NL_response(client, q, nodes, [])

    driver.close()

if __name__ == "__main__":
    main()