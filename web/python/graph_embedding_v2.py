"""
Train GraphSAGE embeddings locally using DGL and write them back to Neo4j AuraDB.
Not using AuraDS. WHich might be free but I'm not figuring that out.
"""

"""
graph_embedding.py
Train GraphSAGE embeddings locally using PyTorch Geometric
and write them back to Neo4j AuraDB.
"""

"""
graph_embedding.py
Train GraphSAGE embeddings locally using PyTorch Geometric
and write them back to Neo4j AuraDB.
"""

from neo4j import GraphDatabase
from tqdm import tqdm
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import SAGEConv
import config

NEO4J_URI = config.NEO4J_URI
NEO4J_USER = config.NEO4J_USERNAME
NEO4J_PASS = config.NEO4J_PASSWORD

EMBED_DIM = 384
HIDDEN_DIM = 128
EPOCHS = 10
LR = 1e-3

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
print("Connected to Neo4j Aura instance")

def fetch_graph_data():
    """Fetch all nodes (with featureVector) and relationships from Neo4j."""
    with driver.session() as session:
        nodes = session.run("""
            MATCH (n)
            WHERE n.featureVector IS NOT NULL
            RETURN elementId(n) AS id, n.featureVector AS fv
        """).data()

        rels = session.run("""
            MATCH (a)-[r]->(b)
            RETURN elementId(a) AS src, elementId(b) AS dst, type(r) AS type
        """).data()

    return nodes, rels

nodes, rels = fetch_graph_data()
print(f"Loaded {len(nodes)} nodes and {len(rels)} directed relationships from Neo4j")

node_ids = {n["id"]: i for i, n in enumerate(nodes)}
src = [node_ids[r["src"]] for r in rels if r["src"] in node_ids and r["dst"] in node_ids]
dst = [node_ids[r["dst"]] for r in rels if r["src"] in node_ids and r["dst"] in node_ids]

edge_index = torch.tensor([src, dst], dtype=torch.long)
print(f"Graph built with {len(nodes)} nodes and {edge_index.size(1)} edges")

features = np.vstack([n["fv"] for n in nodes])
x = torch.tensor(features, dtype=torch.float32)
in_dim = x.size(1)
print(f"Feature dimension: {in_dim}")

class GraphSAGE(nn.Module):
    def __init__(self, in_feats, hidden_feats, out_feats):
        super().__init__()
        self.conv1 = SAGEConv(in_feats, hidden_feats)
        self.conv2 = SAGEConv(hidden_feats, out_feats)

    def forward(self, x, edge_index):
        h = self.conv1(x, edge_index)
        h = F.relu(h)
        h = self.conv2(h, edge_index)
        return h

model = GraphSAGE(in_dim, HIDDEN_DIM, EMBED_DIM)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)

print("Training GraphSAGE model...")
model.train()

for epoch in range(EPOCHS):
    optimizer.zero_grad()
    embeds = model(x, edge_index)
    loss = torch.mean((embeds - x) ** 2)  # reconstruction-style self-supervised objective
    loss.backward()
    optimizer.step()
    print(f"Epoch {epoch+1}/{EPOCHS} — Loss: {loss.item():.4f}")

model.eval()
embeddings = model(x, edge_index).detach().cpu().numpy()

def write_embeddings(tx, node_id, emb):
    tx.run("""
        MATCH (n) WHERE elementId(n) = $id
        SET n.graphSageEmbedding = $embedding
    """, id=node_id, embedding=emb.tolist())

print("Writing graphSageEmbedding back to Neo4j...")
with driver.session() as session:
    for n, emb in tqdm(zip(nodes, embeddings), total=len(nodes)):
        session.execute_write(write_embeddings, n["id"], emb)

driver.close()
print("GraphSAGE embeddings successfully written to nodes!")
