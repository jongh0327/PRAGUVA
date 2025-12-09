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

Instructions to run local website:
1) download docker desktop
2) pull from github and add .env to web folder. (might need to add the . back to the file name), .env file contains api keys
3) run: docker compose -f docker-compose.yml up --build (with docker desktop open)
4) wait 15-30 mins the first time the website is built
5) go to http://localhost:8080/
