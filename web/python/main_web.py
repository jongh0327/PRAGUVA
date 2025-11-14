#!/usr/bin/env python3
import os
import argparse
from typing import Any, Dict, List
from neo4j import GraphDatabase
import config

# --- FIX: set Hugging Face cache directory to a writable location ---
hf_cache_dir = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(hf_cache_dir, exist_ok=True)
os.environ["HF_HOME"] = hf_cache_dir

from embedding_search import build_embedding_model, hybrid_search, search_entry_nodes
from multi_hop_search import MultiHopDriver
from LLM import build_genai_client, strip_embeddings, generate_nl_response_from_graph

def main() -> None:
    parser = argparse.ArgumentParser(description="Neo4j + Gemini assistant (Web)")
    parser.add_argument("-q", "--query", required=True, help="User query")
    parser.add_argument("--alpha", type=float, default=0.5, help="Weight for text vs. graph embeddings")
    parser.add_argument("-k", "--top_k", type=int, default=5, help="Number of top results to return")
    parser.add_argument(
        "-s",
        "--search-mode",
        choices=["simple", "bfs"],
        default="simple",
        help="Graph grounding mode: simple = hybrid hits only, bfs = BFS multi-hop",
    )
    args = parser.parse_args()

    q = args.query.strip()
    if not q:
        print("No query provided.")
        return

    # Connect to Neo4j
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
    )

    embedding_model = build_embedding_model()
    client = build_genai_client()
    mh_driver = MultiHopDriver(driver)

    try:
        if args.search_mode == "simple":
            results = hybrid_search(driver, embedding_model, q, alpha=args.alpha, top_k=args.top_k)
            if not results:
                print("(no results)")
                return

            # Seed nodes for LLM
            seed_nodes: List[Dict[str, Any]] = []
            for row in results:
                node = row["node"]
                node_id = row["nodeEid"]
                labels = list(node.labels) if hasattr(node, "labels") else []
                props = dict(node._properties) if hasattr(node, "_properties") else dict(node)
                seed_nodes.append({"id": node_id, "labels": labels, "props": props})

            nodes_for_llm = seed_nodes
            rels_for_llm: List[Dict[str, Any]] = []

        else:
            # BFS mode
            entry_nodes = search_entry_nodes(driver, embedding_model, q, top_k=args.top_k)
            if not entry_nodes:
                print("(no entry nodes found)")
                return

            # Flatten entry nodes
            seed_nodes: List[Dict[str, Any]] = []
            for row in entry_nodes:
                node = row["node"]
                node_id = row["nodeEid"]
                labels = list(node.labels) if hasattr(node, "labels") else []
                props = dict(node._properties) if hasattr(node, "_properties") else dict(node)
                seed_nodes.append({"id": node_id, "labels": labels, "props": props})

            if not seed_nodes:
                print("(no seed nodes for BFS)")
                return

            query_embedding = embedding_model.encode(q).tolist()
            nodes_for_llm, rels_for_llm = mh_driver.two_hop_via_python(seed_nodes=seed_nodes, query_embedding=query_embedding)

        # Strip embeddings before sending to LLM
        clean_nodes, clean_rels = strip_embeddings(nodes_for_llm, rels_for_llm)
        answer = generate_nl_response_from_graph(client, q, clean_nodes, clean_rels)

        # Print only the LLM answer so PHP can capture it
        print(answer)

    finally:
        driver.close()


if __name__ == "__main__":
    main()