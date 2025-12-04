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
        help="User question"
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

    q = args.query.strip()
    if not q:
        print(json.dumps({"error": "No query provided"}))
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
            q,
            top_k=args.top_entry,
        )

        if not entry_nodes:
            print(json.dumps({"error": "No entry nodes found"}))
            return

        # 2. Convert Neo4j results into GraphRAG seed nodes
        seed_nodes = extract_seed_nodes(entry_nodes)
        if not seed_nodes:
            print(json.dumps({"error": "No seed nodes available"}))
            return

        # 3. Encode user query for BFS scoring
        query_embedding = embedding_model.encode(q).tolist()

        # 0–1 BFS multi-hop expansion
        nodes_for_llm, rels_for_llm = mh_driver.two_hop_via_python(
            seed_nodes=seed_nodes,
            query_embedding=query_embedding,
            top_per_label=args.top_per_label
        )

        # 4. Strip embeddings (clean for LLM)
        clean_nodes, clean_rels = strip_embeddings(nodes_for_llm, rels_for_llm)

        # 5. Generate answer using Gemini
        answer = generate_nl_response_from_graph(
            client,
            q,
            clean_nodes,
            clean_rels,
        )

        # 6. Convert to JSON-friendly format for frontend (Cytoscape.js compatible)
        cy_nodes = []
        for n in clean_nodes:
            node_labels = n.get("labels", [])
            # Remove "Searchable" from labels
            filtered_labels = [label for label in node_labels if label != "Searchable"]
            label_str = " | ".join(filtered_labels) if filtered_labels else "Initial Node"
            
            cy_nodes.append({
                "data": {
                    "id": n["id"],
                    "label": label_str,
                    "nodeType": filtered_labels[0] if filtered_labels else "Initial",
                    **n["props"]
                }
            })

        cy_edges = []
        for r in clean_rels:
            source = r.get("source") or r.get("start") or ""
            target = r.get("target") or r.get("end") or ""
            cy_edges.append({
                "data": {
                    "id": r.get("id") or f"{source}_{target}",
                    "source": source,
                    "target": target,
                    "type": r.get("type") or r.get("rel_type") or ""
                }
            })

        result = {
            "assistant": answer,
            "graph": {
                "nodes": cy_nodes,
                "edges": cy_edges
            }
        }

        print(json.dumps(result))

    finally:
        driver.close()


if __name__ == "__main__":
    main()