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
    courses = search_by_embedding(driver, embedding_model, query_text, "course_embeddings", top_k)
    return {
        "professors": professors,
        "courses": courses
    }


"""
End embedding similarity code
"""

def build_gemini():
    """Create a Gemini model for NL generation from Neo4j results."""
    genai.configure(api_key=config.GEMINI_API_KEY)
    return genai.GenerativeModel(
        getattr(config, "GEMINI_MODEL", "gemini-flash-latest"),
        system_instruction=getattr(config, "GEMINI_SYSTEM_PROMPT", "You are a helpful assistant.")
    )

def generate_NL_response(gemini, q: str, professors: List[Dict[str, Any]], courses: List[Dict[str, Any]]) -> None:
    try:
        # Combine results for Gemini
        all_rows = []

        for row in professors:
            node = row['node']
            props = dict(node._properties) if hasattr(node, '_properties') else dict(node)
            all_rows.append({
                "type": "Professor",
                "score": row['score'],
                **props
            })

        for row in courses:
            node = row['node']
            props = dict(node._properties) if hasattr(node, '_properties') else dict(node)
            all_rows.append({
                "type": "Course",
                "score": row['score'],
                **props
            })

        # Create a custom prompt for embedding-based results
        json_rows = json.dumps(all_rows, ensure_ascii=False, indent=2)

        user_prompt = config.GEMINI_USER_PROMPT.format(
            question=q,
            results=json_rows
        )

        # Generate Gemini response
        resp = gemini.generate_content(user_prompt)
        answer = (resp.text or "").strip()

        if answer:
            print("\n--- Answer ---")
            print(answer)

    except Exception as e:
        print(f"\n--- Answer ---\nGEMINI ERROR: {e}")

    
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
                    props = {key: value for key, value in dict(node._properties).items() if key != 'descriptionEmbedding'}
                else:
                    props = {key: value for key, value in dict(node).items() if key != 'descriptionEmbedding'}
                print(f"{i}. [Score: {score:.4f}] {props}")
        else:
            print("(no results)")

        # Generate natural language answer with Gemini
        generate_NL_response(gemini, q, professors, courses)

    driver.close()

if __name__ == "__main__":
    main()
