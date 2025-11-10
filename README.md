Graph RAG interface for UVA's academic knowledge graph.
Currently focuses on our Academic graph.

Graph update pipeline:
1. Update Graph on Aura
2. Delete existing embeddings by running two Cypher queries: 
    a. MATCH (n)
       WHERE n.featureVector IS NOT NULL
       REMOVE n.featureNode
    b. MATCH (n)
       WHERE n.graphsageEmbedding IS NOT NULL
       REMOVE n.featureNode
3. Run embeddings.py
4. Run graph_embedding.py
5. Create vector indexes by running two Cypher queries:
    CREATE VECTOR INDEX searchable_feature_index
FOR (n:Searchable)
ON (n.featureVector)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }
};