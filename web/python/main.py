#!/usr/bin/env python3
import argparse
from typing import Any, Dict, List

from neo4j import GraphDatabase
import config

from embedding_search import (
    build_embedding_model,
    hybrid_search,
    search_entry_nodes,
)
from multi_hop_search import MultiHopDriver
from LLM import (
    build_genai_client,
    strip_embeddings,
    generate_nl_response_from_graph,
    generate_nl_response_with_search,
)


def _print_results(results: List[Dict[str, Any]]) -> None:
    """
    Pretty-print hybrid search results (for SIMPLE mode).
    Expects each row to have: node, combinedScore, nodeEid.
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


def _print_bfs_results(results: List[Dict[str, Any]]) -> None:
    """
    Pretty-print flat entry-node results for BFS mode.
    Each row has: node, score, nodeEid.
    """
    print("\n--- Entry Nodes (BFS seed candidates) ---")
    if not results:
        print("(no results)")
        return

    for i, row in enumerate(results, 1):
        node = row["node"]
        score = row.get("score", 0.0)
        node_id = row.get("nodeEid")

        if hasattr(node, "_properties"):
            props = dict(node._properties)
            labels = list(node.labels)
        else:
            props = dict(node)
            labels = []

        props = {
            k: v
            for k, v in props.items()
            if "embedding" not in k.lower() and not k.lower().endswith("vector")
        }

        label_str = ",".join(labels) if labels else "Node"
        print(f"  {i}. [{label_str}] [Score: {score:.4f}] [id={node_id}]")
        for key, value in props.items():
            print(f"     {key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Neo4j + Gemini assistant")
    parser.add_argument(
        "-t",
        "--test",
        action="store_true",
        help="Run both Gemini models (GraphRAG and Search-based)",
    )
    parser.add_argument(
        "-a",
        "--alpha",
        type=float,
        default=0.5,
        help="Weight for text vs. graph embeddings (0=graph only, 1=text only) [SIMPLE mode]",
    )
    parser.add_argument(
        "-k",
        "--top_k",
        type=int,
        default=5,
        help="Number of top results to return",
    )
    parser.add_argument(
        "-s",
        "--search-mode",
        choices=["simple", "bfs"],
        default="simple",
        help=(
            "Graph grounding mode:\n"
            "  simple = use hybrid search hits as nodes only\n"
            "  bfs    = use search_professors_and_courses + 0–1 BFS multi-hop"
        ),
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

    # Initialize MultiHopDriver for 0–1 BFS
    mh_driver = MultiHopDriver(driver)

    print("Neo4j + Gemini GraphRAG")
    print(f"Embedding Model: {getattr(config, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}")
    print(f"NL Generation (Gemini): {config.GEMINI_MODEL}")
    print(f"Search mode: {args.search_mode}")
    if args.search_mode == "simple":
        print(f"Alpha (hybrid text/graph weight): {args.alpha}")
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

            if not q:
                continue

            if args.search_mode == "simple":
                # -------- SIMPLE MODE: hybrid_search only --------
                results = hybrid_search(
                    driver,
                    embedding_model,
                    q,
                    alpha=args.alpha,
                    top_k=args.top_k,
                )
                print(
                    f"[DEBUG] main(): SIMPLE mode, received {len(results)} results from hybrid_search()"
                )

                if not results:
                    print("(no results)")
                    continue

                _print_results(results)

                # Seed nodes for LLM: just the hybrid hits, no relationships
                seed_nodes: List[Dict[str, Any]] = []
                for row in results:
                    node = row["node"]
                    node_id = row["nodeEid"]
                    labels = list(node.labels) if hasattr(node, "labels") else []
                    props = (
                        dict(node._properties)
                        if hasattr(node, "_properties")
                        else dict(node)
                    )
                    seed_nodes.append(
                        {"id": node_id, "labels": labels, "props": props}
                    )

                nodes_for_llm = seed_nodes
                rels_for_llm: List[Dict[str, Any]] = []
                print(
                    f"\n[Graph grounding] SIMPLE: using {len(nodes_for_llm)} nodes, 0 relationships"
                )

            else:
                # -------- BFS MODE: use search_professors_and_courses + 0–1 BFS --------
                entry_nodes = search_entry_nodes(
                    driver,
                    embedding_model,
                    q,
                    top_k=args.top_k,
                )
                print(
                    f"[DEBUG] main(): BFS mode, received {len(entry_nodes)} entry nodes from search_professors_and_courses()"
                )

                if not entry_nodes:
                    print("(no entry nodes found)")
                    continue

                _print_bfs_results(entry_nodes)

                # Flatten entry nodes into seed_nodes
                seed_nodes: List[Dict[str, Any]] = []
                for row in entry_nodes:
                    node = row["node"]
                    node_id = row["nodeEid"]
                    labels = list(node.labels) if hasattr(node, "labels") else []
                    props = (
                        dict(node._properties)
                        if hasattr(node, "_properties")
                        else dict(node)
                    )
                    seed_nodes.append(
                        {"id": node_id, "labels": labels, "props": props}
                    )

                if not seed_nodes:
                    print("(no seed nodes for BFS)")
                    continue

                # Query embedding for 0–1 BFS scoring
                query_embedding = embedding_model.encode(q).tolist()

                # 0–1 BFS multi-hop expansion
                nodes_for_llm, rels_for_llm = mh_driver.two_hop_via_python(
                    seed_nodes=seed_nodes,
                    query_embedding=query_embedding,
                )
                print(rels_for_llm[0],rels_for_llm[50])
                print(
                    f"\n[Graph grounding] BFS: nodes={len(nodes_for_llm)}, relationships={len(rels_for_llm)}"
                )

            # ---- Common LLM call for BOTH modes ----
            clean_nodes, clean_rels = strip_embeddings(nodes_for_llm, rels_for_llm)
            answer = generate_nl_response_from_graph(
                client,
                q,
                clean_nodes,
                clean_rels,
            )
            print("\n--- Answer (Graph-based) ---")
            print(answer)

            if args.test:
                s_answer = generate_nl_response_with_search(client, q)
                print("\n--- Answer (Gemini + Google Search) ---")
                print(s_answer)

    finally:
        driver.close()


if __name__ == "__main__":
    main()
