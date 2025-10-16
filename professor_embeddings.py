"""
Creates embeddings for professor descriptions. Adds them to database nodes.
"""

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
import numpy as np
import config

NEO4J_URI = config.NEO4J_URI
NEO4J_USER = config.NEO4J_USERNAME
NEO4J_PASS = config.NEO4J_PASSWORD

print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

def get_professors(tx):
    query = "MATCH (p:Professor) WHERE p.Description IS NOT NULL RETURN elementId(p) AS id, p.Description AS description"
    return list(tx.run(query))

def update_embedding(tx, node_id, embedding):
    query = """
    MATCH (p:Professor) WHERE elementId(p) = $id
    SET p.descriptionEmbedding = $embedding
    """
    tx.run(query, id=node_id, embedding=embedding)

  
with driver.session() as session:
    professors = session.execute_read(get_professors)
    print(f"Found {len(professors)} professors with descriptions")
    for record in professors:
        node_id = record["id"]
        description = record["description"]

        embedding = model.encode(description, convert_to_numpy=True, normalize_embeddings=True)
        # --- Store embedding in Neo4j ---
        session.execute_write(update_embedding, node_id, embedding)

driver.close()
print("✅ Embeddings successfully added to Professor nodes!")
