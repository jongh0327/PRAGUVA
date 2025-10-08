#!/usr/bin/env python3
import os
from neo4j import GraphDatabase
import config as config

# LLM adapters from neo4j-graphrag
from neo4j_graphrag.retrievers import Text2CypherRetriever
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.llm import OpenAILLM, OllamaLLM


def resolve_provider() -> str:
    if config.PROVIDER:
        return config.PROVIDER.lower()
    if config.GROQ_API_KEY:
        return "groq"
    return "ollama"


def build_llm():
    provider = resolve_provider()

    if provider == "groq":
        # Use OpenAI-compatible adapter pointed at Groq
        return OpenAILLM(
            model_name=config.GROQ_MODEL,
            api_key=config.GROQ_API_KEY,           # required
            base_url=config.GROQ_API_BASE,         # Groq endpoint
            model_params={"temperature": config.TEMPERATURE},
        )
        
    raise ValueError(f"Unknown provider: {provider}")


def main():
    # Connect to Neo4j
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )

    # Build LLM and RAG pipeline
    llm = build_llm()

    retriever = Text2CypherRetriever(
        driver=driver,
        llm=llm,
        neo4j_schema=config.SCHEMA_PRIMER,
        examples=config.T2C_EXAMPLES,
    )

    print("Text2Cypher for Recommendations graph (free model). Type 'exit' to quit.")
    print(f"Provider: {config.PROVIDER}")

    while True:
        try:
            q = input("\nQ> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit", ":q"}:
            break

        # 1) Ask the retriever to write Cypher
        r = retriever.search(query_text=q)           # -> RetrieverResult
        cypher = (r.metadata or {}).get("cypher")    # robust access

        if not cypher:
            print("\n--- Cypher ---\n(none generated)")
            print("\n--- Results ---\n(no results)")
            continue

        print("\n--- Cypher ---\n", cypher)

        # 2) Run the Cypher against Neo4j and show results
        try:
            with driver.session() as session:
                rows = session.run(cypher).data()    # list[dict]
        except Exception as e:
            print("\n--- Results ---\nQUERY ERROR:", e)
            continue

        if not rows:
            print("\n--- Results ---\n(0 rows)")
            continue

        # Pretty-print simple tabular results
        print("\n--- Results ---")
        for i, row in enumerate(rows, 1):
            print(f"{i}. {row}")

    driver.close()


if __name__ == "__main__":
    main()
