import os

# --- Choose LLM provider ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Neo4j ---
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-flash-latest"

GEMINI_SYSTEM_PROMPT = (
    "You are a precise, helpful assistant for natural-language graph Q&A. "
    "Explain results clearly, cite concrete entities from the provided rows, "
    "and NEVER invent facts that aren’t present. If results are empty, "
    "state that plainly and suggest a more specific follow-up."
)

GEMINI_USER_PROMPT = """Question: {question}
    Results :
    {results}

    Please provide a helpful, natural language answer to the user's question based on these search results.
    Focus on the most relevant items (highest similarity scores) and explain how they relate to the question.

    Also, note that 1000~4000 level courses are undergrad level and those over 5000s are graduate courses.    
    Do not put information about Node IDs, course IDs, instructor IDs and such in the response.
    They are for internal datakeeping within the graph only. 
    Only exception is the Course Number such as CS 3100. Those, you can show.
    When the query asks for papers or courses taught by a professor, list all that are available.

    For Course-Professor relationships, the semesters that specific professor taught the course is in the relationship(edge's) property.
    Don't list all the semester the course was taught in the school. Not all of them were taught by that professor.
    Just list the semester where that specific professor taught the course.
"""