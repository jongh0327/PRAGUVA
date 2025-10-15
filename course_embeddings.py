"""
Creates embeddings for course descriptions. Adds them to database nodes.
"""

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
import numpy as np

NEO4J_URI = "key"
NEO4J_USER = "key"
NEO4J_PASS = "key"

print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

def get_courses(tx):
    query = "MATCH (c:Course) WHERE c.Description IS NOT NULL RETURN elementId(c) AS id, c.Description AS description"
    return list(tx.run(query))

def update_embedding(tx, node_id, embedding):
    query = """
    MATCH (c:Course) WHERE elementId(c) = $id
    SET c.descriptionEmbedding = $embedding
    """
    tx.run(query, id=node_id, embedding=embedding)

  
with driver.session() as session:
    courses = session.execute_read(get_courses)
    print(f"Found {len(courses)} courses with descriptions")
    for record in courses:
        node_id = record["id"]
        description = record["description"]

        embedding = model.encode(description, convert_to_numpy=True, normalize_embeddings=True)
        # --- Store embedding in Neo4j ---
        session.execute_write(update_embedding, node_id, embedding)

driver.close()
print("✅ Embeddings successfully added to Course nodes!")
