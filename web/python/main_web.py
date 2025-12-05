#!/usr/bin/env python3
import os
import argparse
import json
from typing import Any, Dict, List

from neo4j import GraphDatabase
import config

# HuggingFace cache (safe for server environments)
hf_cache_dir = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(hf_cache_dir, exist_ok=True)
os.environ["HF_HOME"] = hf_cache_dir

from embedding_search import (
    build_embedding_model,
    search_entry_nodes,
)
from multi_hop_search import MultiHopDriver
from LLM import (
    build_genai_client,
    strip_embeddings,
    generate_nl_response_from_graph,
)


def extract_seed_nodes(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract ID, labels, and properties from Neo4j entry nodes."""
    seed_nodes: List[Dict[str, Any]] = []
    for row in rows:
        node = row["node"]
        node_id = row["nodeEid"]

        labels = list(node.labels) if hasattr(node, "labels") else []
        props = dict(node._properties) if hasattr(node, "_properties") else dict(node)

        seed_nodes.append({
            "id": node_id,
            "labels": labels,
            "props": props
        })

    return seed_nodes


def main() -> None:
    parser = argparse.ArgumentParser(description="Web entrypoint for Neo4j + Gemini")
    parser.add_argument(
        "-q",
        "--query",
        required=True,
        help="User question or JSON payload"
    )
    parser.add_argument(
        "-k",
        "--top_entry",
        type=int,
        default=5,
        help="Number of entry nodes"
    )
    parser.add_argument(
        "-l",
        "--top_per_label",
        type=int,
        default=5,
        help="Number top h neighbors per label",
    )
    args = parser.parse_args()

    # Parse the query parameter - it could be JSON payload or plain text
    query_input = args.query.strip()
    if not query_input:
        print(json.dumps({"assistant": "No query provided.", "raw_nodes": [], "raw_edges": []}))
        return

    # Try to parse as JSON payload
    user_query = query_input
    chat_history = []
    transcript = None
    
    try:
        payload = json.loads(query_input)
        if isinstance(payload, dict):
            user_query = payload.get("user_input", query_input)
            chat_history = payload.get("history", [])
            transcript = payload.get("transcript", None)
    except json.JSONDecodeError:
        # Not JSON, treat as plain text query
        user_query = query_input

    if not user_query:
        print(json.dumps({"assistant": "No user query in payload.", "raw_nodes": [], "raw_edges": []}))
        return

    # Connect to Neo4j
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )

    embedding_model = build_embedding_model()
    client = build_genai_client()
    mh_driver = MultiHopDriver(driver)

    try:
        # 1. Find entry nodes using embedding search
        entry_nodes = search_entry_nodes(
            driver,
            embedding_model,
            user_query,
            top_k=args.top_entry,
        )

        if not entry_nodes:
            print(json.dumps({"assistant": "No entry nodes found.", "raw_nodes": [], "raw_edges": []}))
            return

        # 2. Convert Neo4j results into GraphRAG seed nodes
        seed_nodes = extract_seed_nodes(entry_nodes)
        if not seed_nodes:
            print(json.dumps({"assistant": "No seed nodes available.", "raw_nodes": [], "raw_edges": []}))
            return

        # 3. Encode user query for BFS scoring
        query_embedding = embedding_model.encode(user_query).tolist()

        # 0–1 BFS multi-hop expansion (same as main.py)
        nodes_for_llm, rels_for_llm = mh_driver.two_hop_via_python(
            seed_nodes=seed_nodes,
            query_embedding=query_embedding,
            top_per_label=args.top_per_label
        )

        # 4. Strip embeddings (clean for LLM)
        clean_nodes, clean_rels = strip_embeddings(nodes_for_llm, rels_for_llm)

        # 5. Generate answer using Gemini with context
        # Build context string with history and transcript if available
        context_parts = []
        
        if transcript:
            context_parts.append(f"Reference Document:\n{transcript}\n")
        
        if chat_history:
            context_parts.append("Previous Conversation:")
            for msg in chat_history[-5:]:  # Last 5 messages
                context_parts.append(f"User: {msg.get('user', '')}")
                context_parts.append(f"Assistant: {msg.get('assistant', '')}")
            context_parts.append("")
        
        # Add current query with context
        full_query = user_query
        if context_parts:
            context_str = "\n".join(context_parts)
            full_query = f"{context_str}\nCurrent Question: {user_query}"

        answer = generate_nl_response_from_graph(
            client,
            full_query,
            clean_nodes,
            clean_rels,
        )

        # 6. Return RAW nodes and edges (NO Cytoscape transformation)
        # Frontend will transform on-demand when Graph button is clicked
        result = {
            "assistant": answer,
            "raw_nodes": clean_nodes,  # Raw format from Neo4j
            "raw_edges": clean_rels     # Raw format from Neo4j
        }

        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({
            "assistant": f"Error: {str(e)}",
            "raw_nodes": [],
            "raw_edges": []
        }))
    finally:
        driver.close()


if __name__ == "__main__":
    main()