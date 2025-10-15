#!/usr/bin/env python3
import os
import json
from neo4j import GraphDatabase
import config
from typing import Any, Dict, List

# LLM adapters from neo4j-graphrag
from neo4j_graphrag.retrievers import Text2CypherRetriever
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.llm import OpenAILLM, OllamaLLM
import google.generativeai as genai

def resolve_provider() -> str:
    if config.PROVIDER:
        return config.PROVIDER.lower()
    if config.GROQ_API_KEY:
        return "groq"
    return "ollama"


def build_t2c_llm():
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

def build_gemini():
    """Create a Gemini model for NL generation from Neo4j results."""
    genai.configure(api_key=config.GEMINI_API_KEY)
    return genai.GenerativeModel(
        getattr(config, "GEMINI_MODEL", "gemini-flash-latest"),
        system_instruction=getattr(config, "GEMINI_SYSTEM_PROMPT", "You are a helpful assistant.")
    )
    
def _rows_to_jsonable(rows: List[Dict[str, Any]], max_rows: int = 50) -> List[Dict[str, Any]]:
    """Make Neo4j rows JSON-serializable (truncate for safety)."""
    def serialize(val):
        # Try raw JSON; otherwise coerce common Neo4j types
        try:
            json.dumps(val)
            return val
        except TypeError:
            # Neo4j Node/Relationship often carry _properties
            if hasattr(val, "_properties"):
                return dict(val._properties)
            # Fallback to string
            return str(val)

    out = []
    for i, row in enumerate(rows):
        if i >= max_rows:
            break
        out.append({k: serialize(v) for k, v in row.items()})
    return out

def generate_nl_answer(gemini_model, question: str, cypher: str, rows: List[Dict[str, Any]]) -> str:
    """
    Use Gemini to turn raw rows into a helpful, concise answer.
    """
    json_rows = _rows_to_jsonable(rows, max_rows=50)
    rows_preview = json.dumps(json_rows, ensure_ascii=False, indent=2)

    user_prompt = config.GEMINI_USER_PROMPT.format(
        question=question,
        cypher=cypher,
        rows_preview=rows_preview,
    )

    resp = gemini_model.generate_content(user_prompt)
    
    return (resp.text or "").strip()

def main():
    # Connect to Neo4j
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )

    # Build LLM and RAG pipeline
    t2c_llm = build_t2c_llm()
    gemini = build_gemini()

    retriever = Text2CypherRetriever(
        driver=driver,
        llm=t2c_llm,
        neo4j_schema=config.SCHEMA_PRIMER,
        examples=config.T2C_EXAMPLES,
    )

    print("Text2Cypher for Recommendations graph (free model). Type 'exit' to quit.")
    print(f"Provider (Text2Cypher): {config.PROVIDER}")
    print(f"NL Generation (Gemini): {config.GEMINI_MODEL}")

    while True:
        try:
            q = input("\nQ> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit", ":q"}:
            break

        # 1) Text -> Cypher
        r = retriever.search(query_text=q)           # -> RetrieverResult
        cypher = (r.metadata or {}).get("cypher")    # robust access

        if not cypher:
            print("\n--- Cypher ---\n(none generated)")
            print("\n--- Results ---\n(no results)")
            try:
                ans = generate_nl_answer(gemini, q, "(none)", [])
                if ans:
                    print("\n--- Answer ---\n" + ans)
            except Exception:
                pass
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
        else:
            print("\n--- Results ---")
            for i, row in enumerate(rows, 1):
                print(f"{i}. {row}")

        # 3) NL response with Gemini
        try:
            answer = generate_nl_answer(gemini, q, cypher, rows)
            print("\n--- Answer ---\n" + (answer or "(no text)"))
        except Exception as e:
            print("\n--- Answer ---\nGEMINI ERROR:", e)

    driver.close()


if __name__ == "__main__":
    main()
