"""
Train a GraphSAGE model in Neo4j GDS using the previously created 'featureVector'
node properties. Writes the resulting structural+semantic embeddings back to
each node as 'graphsageEmbedding'.
"""

from neo4j import GraphDatabase
import web.python.config as config

driver = GraphDatabase.driver(
    config.NEO4J_URI,
    auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
)

GRAPH_NAME = "full_graph"
EMBEDDING_PROPERTY = "graphsageEmbedding"
FEATURE_PROPERTY = "featureVector"
EMBEDDING_DIM = 256  
EPOCHS = 20
BATCH_SIZE = 512
LEARNING_RATE = 0.01
RELATIONSHIP_TYPES = [
    "RELATES_TO",
    "SPECIALIZES_IN",
    "AUTHORED",
    "BELONGS_TO",
    "TAUGHT_IN",
    "REQUIRES",
    "MAJOR_REQUIRES",
    "MINOR_REQUIRES"
]

def project_graph(tx):
    """
    Projects all node labels and the specified relationship types into a GDS in-memory graph.
    """
    rel_filter = "|".join(RELATIONSHIP_TYPES)
    query = f"""
    CALL gds.graph.project(
        $graph_name,
        ['Course', 'Major', 'Minor', 'Professor', 'Paper', 'Department', 'Topic'],
        {{
            RELATES_TO: {{ type: 'RELATES_TO', orientation: 'NATURAL' }},
            SPECIALIZES_IN: {{ type: 'SPECIALIZES_IN', orientation: 'NATURAL' }},
            AUTHORED: {{ type: 'AUTHORED', orientation: 'NATURAL' }},
            BELONGS_TO: {{ type: 'BELONGS_TO', orientation: 'NATURAL' }},
            TAUGHT_IN: {{ type: 'TAUGHT_IN', orientation: 'NATURAL' }},
            REQUIRES: {{ type: 'REQUIRES', orientation: 'NATURAL' }},
            MAJOR_REQUIRES: {{ type: 'MAJOR_REQUIRES', orientation: 'NATURAL' }},
            MINOR_REQUIRES: {{ type: 'MINOR_REQUIRES', orientation: 'NATURAL' }}
        }},
        {{
            nodeProperties: [$feature_property]
        }}
    )
    YIELD graphName, nodeCount, relationshipCount
    RETURN graphName, nodeCount, relationshipCount
    """
    return tx.run(query, graph_name=GRAPH_NAME, feature_property=FEATURE_PROPERTY).data()



def train_graphsage(tx):
    query = f"""
    CALL gds.beta.graphSage.train(
        $graph_name,
        {{
            featureProperties: [$feature_property],
            embeddingDimension: $embedding_dim,
            batchSize: $batch_size,
            epochs: $epochs,
            learningRate: $learning_rate,
            activationFunction: 'relu',
            aggregator: 'mean'
        }}
    )
    YIELD modelInfo
    RETURN modelInfo
    """
    return tx.run(query,
                  graph_name=GRAPH_NAME,
                  feature_property=FEATURE_PROPERTY,
                  embedding_dim=EMBEDDING_DIM,
                  batch_size=BATCH_SIZE,
                  epochs=EPOCHS,
                  learning_rate=LEARNING_RATE).data()




def write_embeddings(tx):
    query = f"""
    CALL gds.beta.graphSage.write(
        $graph_name,
        {{
            featureProperties: [$feature_property],
            embeddingProperty: $embedding_property,
            embeddingDimension: $embedding_dim
        }}
    )
    YIELD nodePropertiesWritten, computeMillis
    RETURN nodePropertiesWritten, computeMillis
    """
    return tx.run(query,
                  graph_name=GRAPH_NAME,
                  feature_property=FEATURE_PROPERTY,
                  embedding_property=EMBEDDING_PROPERTY,
                  embedding_dim=EMBEDDING_DIM).data()


def drop_graph(tx):
    tx.run("CALL gds.graph.drop($graph_name)", graph_name=GRAPH_NAME)


if __name__ == "__main__":
    with driver.session() as session:
        print(f"Projecting graph '{GRAPH_NAME}' into memory...")
        result = session.execute_write(project_graph)
        print(result)

        print("\nTraining GraphSAGE model...")
        info = session.execute_write(train_graphsage)
        print(info)

        print("\nWriting embeddings back to Neo4j...")
        stats = session.execute_write(write_embeddings)
        print(stats)

        print("\nDropping in-memory graph...")
        session.execute_write(drop_graph)

    driver.close()
    print(f"\nGraphSAGE embeddings successfully written as '{EMBEDDING_PROPERTY}'!")
