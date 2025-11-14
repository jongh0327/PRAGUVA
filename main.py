# main.py
#!/usr/bin/env python3
import argparse
from typing import Any, Dict, List

from neo4j import GraphDatabase
import config

from embedding_search import build_embedding_model, hybrid_search
from LLM import (
    build_genai_client,
    generate_nl_response_from_graph,
    generate_nl_response_with_search,
)


def _print_results(results: List[Dict[str, Any]]) -> None:
    """
    Pretty-print hybrid search results (same formatting as your original script).
    """
    print("\n--- Top Matching Nodes (Hybrid Ranked) ---")
    for i, row in enumerate(results, 1):
        node = row["node"]
        score = row["combinedScore"]
        node_id = row["nodeEid"]

        # Extract clean properties (drop embeddings for console readability)
        if hasattr(node, "_properties"):
            props = {
                k: v
                for k, v in dict(node._properties).items()
                if (not k.endswith("Embedding") and not k.endswith("Vector"))
            }
        else:
            props = {
                k: v
                for k, v in dict(node).items()
                if (not k.endswith("Embedding") and not k.endswith("Vector"))
            }

        label = list(node.labels)[0] if hasattr(node, "labels") else "Node"
        print(f"{i}. [{label}] [Score: {score:.4f}] [id={node_id}]")
        for key, value in props.items():
            print(f"   {key}: {value}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Neo4j + Gemini assistant")
    parser.add_argument(
        "-t",
        "--test",
        action="store_true",
        help="Run both Gemini models (GraphRAG and Search-based)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.5,
        help="Weight for text vs. graph embeddings (0=graph only, 1=text only)",
    )
    parser.add_argument(
        "--top_k",
        type=int,
        default=5,
        help="Number of top results to return",
    )
    args = parser.parse_args()

    # Connect to Neo4j
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
    )

    # Build embedding model and Gemini for NL generation
    embedding_model = build_embedding_model()
    client = build_genai_client()

    print("Embedding-based search for All Nodes (Professors, Courses, Papers, etc.)")
    print(f"Embedding Model: {getattr(config, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}")
    print(f"NL Generation (Gemini): {config.GEMINI_MODEL}")
    print(f"Alpha (text weight): {args.alpha}")
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

            # 1) Hybrid search
            results = hybrid_search(
                driver,
                embedding_model,
                q,
                alpha=args.alpha,
                top_k=args.top_k,
            )
            print(f"[DEBUG] main(): received {len(results)} results from hybrid_search()")

            if not results:
                print("(no results)")
                continue

            _print_results(results)

            # 2) Build 'nodes' payload like in your original script:
            #    just the properties of the matched nodes (no ids/labels)
            nodes = [
                dict(node._properties) if hasattr(node, "_properties") else dict(node)
                for node in [r["node"] for r in results]
            ]

            # 3) Graph-based NL answer (using nodes only, relationships empty)
            answer = generate_nl_response_from_graph(client, q, nodes, [])
            print("\n--- Answer (Graph-based) ---")
            print(answer)

            # 4) Optional: Search-grounded Gemini answer when --test is enabled
            if args.test:
                s_answer = generate_nl_response_with_search(client, q)
                print("\n--- Answer (Gemini + Google Search) ---")
                print(s_answer)

    finally:
        driver.close()


if __name__ == "__main__":
    main()
