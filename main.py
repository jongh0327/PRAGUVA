#!/usr/bin/env python3
import argparse
from typing import Dict, Any
from neo4j import GraphDatabase

import config
from entry_node_search import build_embedding_model, search_professors_and_courses
from multi_hop_search import MultiHopDriver
from LLM import (
    build_genai_client,
    strip_embeddings,
    generate_nl_response_from_graph,
    generate_nl_response_with_search,
)


def _print_results(title: str, rows: list[Dict[str, Any]]) -> None:
    print(f"\n--- {title} ---")
    if not rows:
        print("(no results)")
        return
    for i, row in enumerate(rows, 1):
        node = row["node"]
        score = row["score"]
        node_id = row["nodeEid"]
        if hasattr(node, "_properties"):
            props = {k: v for k, v in dict(node._properties).items() if "embedding" not in k.lower()}
        else:
            props = {k: v for k, v in dict(node).items() if "embedding" not in k.lower()}
        print(f"{i}. [Score: {score:.4f}] [id={node_id}]")
        for k, v in props.items():
            print(f"{k}: {v}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Neo4j + Gemini assistant (modular with MultiHopDriver)")
    parser.add_argument("-t", "--test", action="store_true",
                        help="Run both Gemini modes (GraphRAG & Search-grounded)")
    args = parser.parse_args()

    # Connect to Neo4j
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )

    # Build embedding model and Gemini for NL generation
    embedding_model = build_embedding_model()
    client = build_genai_client()

    # Initialize our new MultiHopDriver wrapper
    mh_driver = MultiHopDriver(driver)

    print("Embedding-based search for Professors and Courses. Type 'exit' to quit.")
    print(f"Embedding Model: {getattr(config, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}")
    print(f"NL Generation (Gemini): {config.GEMINI_MODEL}")
    if args.test:
        print("Test mode: Comparing GraphRAG-style NL vs. Search-grounded NL")

    try:
        while True:
            try:
                q = input("\nQ> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if q.lower() in {"exit", "quit", ":q"}:
                break

            # Step 1: search seed nodes by embeddings
            results = search_professors_and_courses(driver, embedding_model, q, top_k=3)
            professors = results["professors"]
            courses = results["courses"]

            _print_results("Top Professors", professors)
            _print_results("Top Courses", courses)

            entry_eids = list({row["nodeEid"] for row in professors + courses})
            if not entry_eids:
                print("(no entry nodes found)")
                continue

            # Step 2: compute query embedding for similarity ranking inside graph traversal
            query_embedding = embedding_model.encode(q).tolist()

            # Step 3: use MultiHopDriver for multi-hop expansion
            nodes, relationships = mh_driver.two_hop_via_python(
                entry_eids,
                max_nodes=1000,
                max_rels=4000,
                max_hop1_neighbors=100,
                one_hop_kwargs={
                    "query_embedding": query_embedding,
                    "embedding_prop": "descriptionEmbedding",
                    "top_per_label": 10,
                    # "relationship_types": ["TEACHES", "MENTORS"],
                    # "label_whitelist": ["Professor", "Course", "Department"],
                },
            )

            print(f"\n[Subgraph] nodes: {len(nodes)}, relationships: {len(relationships)}")

            # Step 4: generate natural-language output via Gemini
            nodes, relationships = strip_embeddings(nodes, relationships)
            answer = generate_nl_response_from_graph(client, q, nodes, relationships)
            if answer:
                print("\n--- Answer (Graph-based) ---")
                print(answer)

            # Optional: Gemini Search-based answer
            if args.test:
                print("#" * 100)
                s_answer = generate_nl_response_with_search(client, q)
                print("\n--- Answer (Gemini + Google Search) ---")
                print(s_answer)

    finally:
        driver.close()


if __name__ == "__main__":
    main()
