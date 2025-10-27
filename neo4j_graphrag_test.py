#!/usr/bin/env python3
import os
import json
from neo4j import GraphDatabase
import config
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
        print_payload_size("Graph JSON prompt", graph_json)

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
    args = parser.parse_args()

    # Connect to Neo4j
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )

    # Build embedding model and Gemini for NL generation
    embedding_model = build_embedding_model()
    client = build_genai_client()

    print("Embedding-based search for Professors and Courses. Type 'exit' to quit.")
    print(f"Embedding Model: {getattr(config, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}")
    print(f"NL Generation (Gemini): {config.GEMINI_MODEL}")
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
        results = search_professors_and_courses(driver, embedding_model, q, top_k=3)
        
        professors = results["professors"]
        courses = results["courses"]
        
        # Display results
        print("\n--- Top Professors ---")
        if professors:
            for i, row in enumerate(professors, 1):
                node = row['node']
                score = row['score']
                node_id = row['nodeEid']
                # Extract node properties
                if hasattr(node, '_properties'):
                    props = {key: value for key, value in dict(node._properties).items() if key != 'descriptionEmbedding'}
                else:
                    props = {key: value for key, value in dict(node).items() if key != 'descriptionEmbedding'}
                print(f"{i}. [Score: {score:.4f}] [id={node_id}]")
                for key,value in props.items():
                    print(f"{key}: {value}")
                print()
        else:
            print("(no results)")
        
        print("\n--- Top Courses ---")
        if courses:
            for i, row in enumerate(courses, 1):
                node = row['node']
                score = row['score']
                node_id = row['nodeEid']
                # Extract node properties
                if hasattr(node, '_properties'):
                    props = {key: value for key, value in dict(node._properties).items() if key != 'descriptionEmbedding'}
                else:
                    props = {key: value for key, value in dict(node).items() if key != 'descriptionEmbedding'}
                print(f"{i}. [Score: {score:.4f}] [id={node_id}]")
                for key,value in props.items():
                    print(f"{key}: {value}")
                print()
        else:
            print("(no results)")

        # Collect Entry seed IDs
        entry_eids = list({row["nodeEid"] for row in professors + courses})

        nodes, relationships = fetch_two_hop_subgraph_apoc(
            driver,
            entry_eids,
            max_level=2
        )
        print(f"\n[Subgraph] nodes: {len(nodes)}, relationships: {len(relationships)}")

        # Generate natural language answer with Gemini
        generate_NL_response(client, q, nodes, relationships)
        
        # Optional search-based NL generation
        if(args.test):
            print("#" * 100)
            generate_NL_response_with_search(client, q)

    driver.close()

if __name__ == "__main__":
    main()
