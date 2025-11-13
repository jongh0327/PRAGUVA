import os

# --- Choose LLM provider ---
PROVIDER = "groq"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Neo4j ---
NEO4J_URI = "neo4j+s://b8e99ab4.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "0_JY9HzSR3WGckN5PRimrD__vLHEXV53MLx2LViUezg"

# --- Gemini ---
GEMINI_API_KEY = "AIzaSyBHpT6rzS7r74HsD9v3Fys_s0Rgpr2GqRM" 
GEMINI_MODEL = "gemini-flash-latest"

GEMINI_SYSTEM_PROMPT = (
    "You are a precise, helpful assistant for natural-language graph Q&A. "
    "Explain results clearly, cite concrete entities from the provided rows, "
    "and NEVER invent facts that aren’t present. If results are empty, "
    "state that plainly and suggest a more specific follow-up."
)

GEMINI_USER_PROMPT = """Question: {question}
    Search Method: Vector similarity search using embeddings
    Results (showing similarity scores where 1.0 is most similar):
    {results}

    Please provide a helpful, natural language answer to the user's question based on these search results.
    Focus on the most relevant items (highest similarity scores) and explain how they relate to the question.

    Also, note that 1000~4000 level courses are undergrad level and those over 5000s are graduate courses.    
"""