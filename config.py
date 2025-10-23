import os

# --- Choose LLM provider ---
PROVIDER = "groq"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Neo4j ---
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# --- Groq (OpenAI-compatible) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_BASE = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-flash-latest"

# --- LLM settings ---
TEMPERATURE = 0

# --- Schema primer & few-shot examples ---
SCHEMA_PRIMER = """
Labels & key properties (use coalesce for variants):
  Course( name|Name: STRING?, ID|Id|id|Number: STRING? )
  Department( Department|name|Name: STRING UNIQUE )
  Professor( name|Name: STRING UNIQUE )

Relationships (only these exist right now):
  (:Professor)-[:BELONGS_TO]->(:Department)
  (:Professor)-[:TAUGHT]->(:Course)

Notes:
  - Read-only Cypher (MATCH/WHERE/RETURN/ORDER/LIMIT) only.
  - Prefer concise outputs (course, department, professor, counts).
  - Use coalesce(...) for property variants; compare case-insensitively via toUpper(...).
  - There is NO direct Course→Department edge; to reach a course's department,
    go Course <-[:TAUGHT]- Professor -[:BELONGS_TO]-> Department.
  - Default LIMIT 20 if not specified.
"""

T2C_EXAMPLES = [
    # 1) Courses taught by a given professor (simple TAUGHT edge)
    "USER INPUT: List all courses taught by Professor Smith.\n"
    "QUERY: MATCH (p:Professor)-[:TAUGHT]->(c:Course) "
    "WHERE toUpper(coalesce(p.name, p.Name)) = toUpper('Professor Smith') "
    "RETURN coalesce(c.name, c.Name) AS course, "
    "       coalesce(c.ID, c.Id, c.id, c.Number) AS courseId "
    "ORDER BY course LIMIT 20",

    # 2) Departments of a given course ID (must go via professors)
    "USER INPUT: Which department does CS101 belong to?\n"
    "QUERY: MATCH (c:Course)<-[:TAUGHT]-(p:Professor)-[:BELONGS_TO]->(d:Department) "
    "WHERE coalesce(c.ID, c.Id, c.id, c.Number) = 'CS101' "
    "RETURN DISTINCT coalesce(d.Department, d.name, d.Name) AS department "
    "ORDER BY department LIMIT 20",

    # 3) Professors in a given department
    "USER INPUT: What professors are in the ECE department?\n"
    "QUERY: MATCH (p:Professor)-[:BELONGS_TO]->(d:Department) "
    "WHERE toUpper(coalesce(d.Department, d.name, d.Name)) = toUpper('ECE') "
    "RETURN DISTINCT coalesce(p.name, p.Name) AS professor "
    "ORDER BY professor LIMIT 20",

    # 4) Courses in a given department (via department’s professors)
    "USER INPUT: Find courses in the ECE department.\n"
    "QUERY: MATCH (p:Professor)-[:BELONGS_TO]->(d:Department) "
    "WHERE toUpper(coalesce(d.Department, d.name, d.Name)) = toUpper('ECE') "
    "MATCH (p)-[:TAUGHT]->(c:Course) "
    "RETURN DISTINCT coalesce(c.name, c.Name) AS course, "
    "       coalesce(c.ID, c.Id, c.id, c.Number) AS courseId "
    "ORDER BY course LIMIT 20",

    # 5) How many courses per department (count distinct courses taught by that dept’s professors)
    "USER INPUT: How many courses are in each department?\n"
    "QUERY: MATCH (p:Professor)-[:BELONGS_TO]->(d:Department) "
    "MATCH (p)-[:TAUGHT]->(c:Course) "
    "RETURN coalesce(d.Department, d.name, d.Name) AS department, "
    "       count(DISTINCT c) AS numCourses "
    "ORDER BY numCourses DESC, department LIMIT 20",

    # 6) What professor teaches CS01
    "USER INPUT: What professor teaches CS01?\n"
    "QUERY: MATCH (p:Professor)-[:TAUGHT]->(c:Course) "
    "WHERE toUpper(toString(coalesce(c.ID, c.Id, c.id, c.Number))) = toUpper('CS01') "
    "RETURN DISTINCT coalesce(p.name, p.Name) AS professor "
    "ORDER BY professor LIMIT 20",
]

GEMINI_SYSTEM_PROMPT = (
    "You are a precise, helpful assistant for natural-language graph Q&A. "
    "Explain results clearly, cite concrete entities from the provided rows, "
    "and NEVER invent facts that aren’t present. If results are empty, "
    "state that plainly and suggest a more specific follow-up."
)

GEMINI_USER_PROMPT = """\
Question:
{question}

Cypher used:
{cypher}

Rows from Neo4j (JSON, up to 50):
{rows_preview}

Write a concise, well-structured answer based ONLY on the rows above:
- 3–8 sentences, specific and grounded (no fabrication).
- Summarize key findings; include counts when relevant.
- Mention a few concrete examples if there are many.
- If no rows, state that and suggest a refined follow-up query.
"""