"""
Creates text embeddings for all key node types (Course, Major, Minor, Professor, Paper, Topic, Department)
and stores them as a numeric list in the 'featureVector' property for each node.

These embeddings will later serve as input features for GraphSAGE or other graph embeddings
to combine text semantics with graph structure.
"""

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
import numpy as np
import web.python.config as config
from tqdm import tqdm

NEO4J_URI = config.NEO4J_URI
NEO4J_USER = config.NEO4J_USERNAME
NEO4J_PASS = config.NEO4J_PASSWORD

print("🚀 Loading embedding model (all-MiniLM-L6-v2)...")
model = SentenceTransformer("all-MiniLM-L6-v2")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

NODE_CONFIGS = {
    "Course": ["Name", "Description"],
    "Major": ["name", "description"],
    "Minor": ["name", "description"],
    "Professor": ["name", "description"],
    "Paper": ["title", "abstract"],
    "Topic": ["topicName"],
    "Department": ["department"]
}



def combine_text(props, fields):
    """Combine multiple string properties into one string for embedding."""
    texts = []
    for f in fields:
        val = props.get(f)
        if val and isinstance(val, str):
            texts.append(val.strip())
    return ". ".join(texts).strip()


def normalize(vec):
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist() if norm > 0 else vec.tolist()



def get_nodes(tx, label, fields):
    """
    Fetch all nodes of a given label with at least one non-null field among 'fields'.
    """
    conditions = " OR ".join([f"n.{f} IS NOT NULL" for f in fields])
    query = f"""
    MATCH (n:{label})
    WHERE {conditions}
    RETURN elementId(n) AS id, properties(n) AS props
    """
    return list(tx.run(query))


def update_embedding(tx, node_id, embedding):
    query = """
    MATCH (n) WHERE elementId(n) = $id
    SET n.featureVector = $embedding
    """
    tx.run(query, id=node_id, embedding=embedding)



with driver.session() as session:
    for label, fields in NODE_CONFIGS.items():
        print(f"\n🧩 Processing {label} nodes...")
        nodes = session.execute_read(get_nodes, label, fields)
        print(f"   Found {len(nodes)} nodes to embed")

        for record in tqdm(nodes):
            node_id = record["id"]
            props = record["props"]
            text = combine_text(props, fields)

            if not text:
                continue

            embedding = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            embedding = normalize(embedding)

            session.execute_write(update_embedding, node_id, embedding)

driver.close()
print("\n✅ All embeddings successfully added to nodes (property: featureVector)")
