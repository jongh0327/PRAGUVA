#!/usr/bin/env python3
import os
import json
from neo4j import GraphDatabase
import config
from typing import Any, Dict, List
from sentence_transformers import SentenceTransformer

# LLM adapters from neo4j-graphrag
from neo4j_graphrag.retrievers import Text2CypherRetriever
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.llm import OpenAILLM, OllamaLLM
import google.generativeai as genai

"""
Begin embedding similarity code
"""

def build_embedding_model():
    model_name = getattr(config, "EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    return SentenceTransformer(model_name)

def search_by_embedding(driver, embedding_model, query_text: str, index_name: str, top_k: int = 6):
    user_embedding = embedding_model.encode(query_text).tolist()

    cypher = """
    CALL db.index.vector.queryNodes($index_name, $top_k, $user_embedding)
    YIELD node, score
    RETURN node, score
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

def search_professors_and_courses(driver, embedding_model, query_text: str, top_k: int = 6):
    professors = search_by_embedding(driver, embedding_model, query_text, "professor_embeddings", top_k)
    courses = search_by_embedding(driver, embedding_model, query_text, "course embeddings", top_k)
    return {
        "professors": professors,
        "courses": courses
    }


"""
End embedding similarity code
"""

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

    # Build embedding model and Gemini for NL generation
    embedding_model = build_embedding_model()
    gemini = build_gemini()

    print("Embedding-based search for Professors and Courses. Type 'exit' to quit.")
    print(f"Embedding Model: {getattr(config, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}")
    print(f"NL Generation (Gemini): {config.GEMINI_MODEL}")

    while True:
        try:
            q = input("\nQ> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit", ":q"}:
            break

        # Search both professor and course embeddings
        results = search_professors_and_courses(driver, embedding_model, q, top_k=6)
        
        professors = results["professors"]
        courses = results["courses"]
        
        # Display results
        print("\n--- Top Professors ---")
        if professors:
            for i, row in enumerate(professors, 1):
                node = row['node']
                score = row['score']
                # Extract node properties
                if hasattr(node, '_properties'):
                    props = dict(node._properties)
                else:
                    props = dict(node)
                print(f"{i}. [Score: {score:.4f}] {props}")
        else:
            print("(no results)")
        
        print("\n--- Top Courses ---")
        if courses:
            for i, row in enumerate(courses, 1):
                node = row['node']
                score = row['score']
                # Extract node properties
                if hasattr(node, '_properties'):
                    props = dict(node._properties)
                else:
                    props = dict(node)
                print(f"{i}. [Score: {score:.4f}] {props}")
        else:
            print("(no results)")

        # Generate natural language answer with Gemini
        try:
            # Combine results for Gemini
            all_rows = []
            for row in professors:
                node = row['node']
                if hasattr(node, '_properties'):
                    props = dict(node._properties)
                else:
                    props = dict(node)
                all_rows.append({
                    "type": "Professor",
                    "score": row['score'],
                    **props
                })
            
            for row in courses:
                node = row['node']
                if hasattr(node, '_properties'):
                    props = dict(node._properties)
                else:
                    props = dict(node)
                all_rows.append({
                    "type": "Course",
                    "score": row['score'],
                    **props
                })
            
            # Create a custom prompt for embedding-based results
            json_rows = json.dumps(all_rows, ensure_ascii=False, indent=2)
            
            user_prompt = f"""Question: {q}

Search Method: Vector similarity search using embeddings

Results (showing similarity scores where 1.0 is most similar):
{json_rows}

Please provide a helpful, natural language answer to the user's question based on these search results. Focus on the most relevant items (highest similarity scores) and explain how they relate to the question."""

            resp = gemini.generate_content(user_prompt)
            answer = (resp.text or "").strip()
            
            if answer:
                print("\n--- Answer ---")
                print(answer)
        except Exception as e:
            print(f"\n--- Answer ---\nGEMINI ERROR: {e}")

    driver.close()

    # # Connect to Neo4j
    # driver = GraphDatabase.driver(
    #     config.NEO4J_URI,
    #     auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    # )

    # # Build LLM and RAG pipeline
    # t2c_llm = build_t2c_llm()
    # gemini = build_gemini()

    # retriever = Text2CypherRetriever(
    #     driver=driver,
    #     llm=t2c_llm,
    #     neo4j_schema=config.SCHEMA_PRIMER,
    #     examples=config.T2C_EXAMPLES,
    # )

    # print("Text2Cypher for Recommendations graph (free model). Type 'exit' to quit.")
    # print(f"Provider (Text2Cypher): {config.PROVIDER}")
    # print(f"NL Generation (Gemini): {config.GEMINI_MODEL}")

    # while True:
    #     try:
    #         q = input("\nQ> ").strip()
    #     except (EOFError, KeyboardInterrupt):
    #         break
    #     if q.lower() in {"exit", "quit", ":q"}:
    #         break

    #     # 1) Text -> Cypher
    #     r = retriever.search(query_text=q)           # -> RetrieverResult
    #     cypher = (r.metadata or {}).get("cypher")    # robust access

    #     if not cypher:
    #         print("\n--- Cypher ---\n(none generated)")
    #         print("\n--- Results ---\n(no results)")
    #         try:
    #             ans = generate_nl_answer(gemini, q, "(none)", [])
    #             if ans:
    #                 print("\n--- Answer ---\n" + ans)
    #         except Exception:
    #             pass
    #         continue

    #     print("\n--- Cypher ---\n", cypher)

    #     # 2) Run the Cypher against Neo4j and show results
    #     try:
    #         with driver.session() as session:
    #             rows = session.run(cypher).data()    # list[dict]
    #     except Exception as e:
    #         print("\n--- Results ---\nQUERY ERROR:", e)
    #         continue

    #     if not rows:
    #         print("\n--- Results ---\n(0 rows)")
    #     else:
    #         print("\n--- Results ---")
    #         for i, row in enumerate(rows, 1):
    #             print(f"{i}. {row}")

    #     # 3) NL response with Gemini
    #     try:
    #         answer = generate_nl_answer(gemini, q, cypher, rows)
    #         print("\n--- Answer ---\n" + (answer or "(no text)"))
    #     except Exception as e:
    #         print("\n--- Answer ---\nGEMINI ERROR:", e)

    # driver.close()


if __name__ == "__main__":
    main()
