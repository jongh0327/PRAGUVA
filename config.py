import os

# --- Choose LLM provider ---
PROVIDER = "groq"

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
Labels & key properties (property variants handled via coalesce):
  Course(name|Name: STRING?, id|Id|ID|Number|`Course ID`: STRING?)
  Department(name|Name|Department: STRING UNIQUE)
  Professor(name|Name: STRING UNIQUE)

Relationships (directional):
  (:Course)-[:BELONGS_TO]->(:Department)
  (:Professor)-[:TAUGHT]->(:Course)

Notes:
  - Ignore legacy labels: Movie, Genre, Person, User, Actor.
  - Read-only Cypher (MATCH/WHERE/RETURN/ORDER/LIMIT).
  - Prefer concise outputs (course name, department, professor, counts).
  - Use coalesce(...) for property key variants; compare names case-insensitively with toUpper(...).
  - Default LIMIT 20 if not specified.
"""

T2C_EXAMPLES = [
# List all courses taught by Professor Smith.
"USER INPUT: List all courses taught by Professor Smith."
"QUERY: MATCH (p:Professor)-[:TAUGHT]->(c:Course) "
"WHERE toUpper(coalesce(p.name, p.Name)) = toUpper('Professor Smith') "
"RETURN coalesce(c.name, c.Name) AS course, "
"       coalesce(c.`Course ID`, c.CourseID, c.ID, c.Id, c.Number, c.id) AS courseId "
"ORDER BY course LIMIT 20",

# Which department does CS101 belong to?
"USER INPUT: Which department does CS101 belong to?"
"QUERY: MATCH (c:Course)-[:BELONGS_TO]->(d:Department) "
"WHERE coalesce(c.`Course ID`, c.CourseID, c.ID, c.Id, c.Number, c.id) = 'CS101' "
"RETURN coalesce(d.name, d.Name, d.Department) AS department",

# Professors teaching in the Computer Science department.
"USER INPUT: Show professors teaching in the Computer Science department."
"QUERY: MATCH (p:Professor)-[:TAUGHT]->(c:Course)-[:BELONGS_TO]->(d:Department) "
"WHERE toUpper(coalesce(d.name, d.Name, d.Department)) = toUpper('Computer Science') "
"RETURN DISTINCT coalesce(p.name, p.Name) AS professor "
"ORDER BY professor LIMIT 20",

# Find courses in the ECE department.
"USER INPUT: Find courses in the ECE department."
"QUERY: MATCH (c:Course)-[:BELONGS_TO]->(d:Department) "
"WHERE toUpper(coalesce(d.name, d.Name, d.Department)) = toUpper('ECE') "
"RETURN coalesce(c.name, c.Name) AS course, "
"       coalesce(c.`Course ID`, c.CourseID, c.ID, c.Id, c.Number, c.id) AS courseId "
"ORDER BY course LIMIT 20",

# How many courses are in each department?
"USER INPUT: How many courses are in each department?"
"QUERY: MATCH (c:Course)-[:BELONGS_TO]->(d:Department) "
"RETURN coalesce(d.name, d.Name, d.Department) AS department, count(c) AS numCourses "
"ORDER BY numCourses DESC LIMIT 20",
]
