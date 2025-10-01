"""
Configuration for Text→Cypher demo.
Pick provider = "groq" (cloud, free tier, faster) or "ollama" (local, slower on CPU).
"""
import os

# --- Choose LLM provider ---
PROVIDER = "groq"   # "groq" or "ollama"

# --- Neo4j ---
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# --- Groq (OpenAI-compatible) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_BASE = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- LLM settings ---
TEMPERATURE = 0

# --- Schema primer & few-shot examples ---
SCHEMA_PRIMER = """
Labels & key properties:
  Movie(title: STRING UNIQUE, released: INT?, imdbId: STRING?)
  User(id: INT? | STRING?)
  Genre(name: STRING)
  Actor(name: STRING)
  Director(name: STRING)
  Person(name: STRING)

Relationships (directional):
  (:User)-[:RATED {rating: INT, timestamp: INT?}]->(:Movie)
  (:Movie)-[:IN_GENRE]->(:Genre)
  (:Actor)-[:ACTED_IN]->(:Movie)
  (:Director)-[:DIRECTED]->(:Movie)
  (:Person)-[:ACTED_IN|:DIRECTED]->(:Movie)

Guidelines:
  - Read-only Cypher (MATCH/WHERE/RETURN/ORDER/LIMIT).
  - Prefer concise outputs (movie title, avg rating, counts).
  - If user asks for "similar movies to <title>", use co-rating pattern via users.
  - For actor queries, use (:Actor {name:'...'})-[:ACTED_IN]->(:Movie).
  - Default LIMIT 20 if not specified.
"""

T2C_EXAMPLES = [
  "USER INPUT: Recommend movies similar to 'The Matrix'. "
  "QUERY: MATCH (:Movie {title:'The Matrix'})<-[:RATED]-(u:User)-[:RATED]->(rec:Movie) "
  "WHERE rec.title <> 'The Matrix' "
  "RETURN DISTINCT rec.title AS title LIMIT 20",

  "USER INPUT: Top 10 Sci-Fi movies by average rating. "
  "QUERY: MATCH (m:Movie)-[:IN_GENRE]->(:Genre {name:'Sci-Fi'})<-[:IN_GENRE]-(:Movie) "
  "MATCH (m)<-[r:RATED]-(:User) "
  "RETURN m.title AS title, round(avg(r.rating),2) AS avgRating, count(r) AS ratings "
  "ORDER BY avgRating DESC, ratings DESC LIMIT 10",

  "USER INPUT: What did user 42 give 5 stars? "
  "QUERY: MATCH (:User {id:42})-[r:RATED {rating:5}]->(m:Movie) "
  "RETURN m.title AS title ORDER BY m.title LIMIT 25"

  "USER INPUT: What movies did Tom Cruise act in? "
  "QUERY: MATCH (a:Actor {name:'Tom Cruise'})-[:ACTED_IN]->(m:Movie) "
  "RETURN m.title AS title ORDER BY m.title LIMIT 20"
]
