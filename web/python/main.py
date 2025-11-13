#!/usr/bin/env python3
import argparse
import json
from typing import Dict, Any
from neo4j import GraphDatabase

import web.python.config as config
from web.python.entry_node_search import build_embedding_model, search_professors_and_courses
from web.python.multi_hop_search import MultiHopDriver
from web.python.LLM import (
    build_genai_client,
    strip_embeddings,
    generate_nl_response_from_graph,
    generate_nl_response_with_search,
)

def run_query(query: str) -> str:
    """Run a single query and return the LLM output as a string."""
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )

    embedding_model = build_embedding_model()
    client = build_genai_client()
    mh_driver = MultiHopDriver(driver)

    results = search_professors_and_courses(driver, embedding_model, query, top_k=3)
    professors = results["professors"]
    courses = results["courses"]

    if not (professors or courses):
        driver.close()
        return "(no entry nodes found)"

    def _row_to_seed(row: Dict[str, Any]) -> Dict[str, Any]:
        node = row["node"]
        node_id = row["nodeEid"]
        labels = list(node.labels) if hasattr(node, "labels") else []
        props = dict(node._properties) if hasattr(node, "_properties") else dict(node)
        return {"id": node_id, "labels": labels, "props": props}

    seed_nodes = [_row_to_seed(r) for r in (professors + courses)]
    query_embedding = embedding_model.encode(query).tolist()

    nodes, relationships = mh_driver.two_hop_via_python(
        seed_nodes=seed_nodes,
        query_embedding=query_embedding,
    )

    nodes, relationships = strip_embeddings(nodes, relationships)
    answer = generate_nl_response_from_graph(client, query, nodes, relationships)

    driver.close()
    return answer or "(no answer generated)"


def main():
    parser = argparse.ArgumentParser(description="Run Neo4j + LLM query")
    parser.add_argument("-q", "--query", type=str, help="User query for the LLM")
    args = parser.parse_args()

    if args.query:
        print(run_query(args.query))
    else:
        # Interactive mode (same as before)
        print("Interactive mode. Type 'exit' to quit.")
        while True:
            q = input("Q> ").strip()
            if q.lower() in {"exit", "quit"}:
                break
            print(run_query(q))


if __name__ == "__main__":
    main()