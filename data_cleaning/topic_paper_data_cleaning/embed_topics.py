#!/usr/bin/env python3

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import os

def embed_topics(csv_path="TopicNode.csv", output_path="topics_with_embeddings.csv"):
    """
    Embed topic names from CSV and save embeddings alongside the data.
    
    Args:
        csv_path: Path to the TopicNode.csv file
        output_path: Path to save the CSV with embeddings
    """
    
    # Check if input file exists
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found!")
        return

    # Load the pre-trained model (same one used for professors)
    print("Loading SentenceTransformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Read the CSV file
    print(f"Reading {csv_path}...")
    df = pd.read_csv(csv_path)
    
    print(f"Found {len(df)} topics to embed")
    
    # Check if topicName column exists
    if 'topicName' not in df.columns:
        print("Error: 'topicName' column not found in CSV!")
        print(f"Available columns: {list(df.columns)}")
        return
    
    # Extract texts to embed (the topic names)
    texts = df['topicName'].fillna('').tolist()
    
    # Generate embeddings with progress tracking
    print("Generating embeddings...")
    print(f"Processing {len(texts)} topics...")
    
    embeddings = model.encode(
        texts, 
        convert_to_numpy=True, 
        normalize_embeddings=True,
        show_progress_bar=True
    )
    
    print("✅ Embedding generation complete!")
    
    # Convert embeddings to list format for CSV storage
    print("Converting embeddings to CSV format...")
    embedding_lists = []
    for i, embedding in enumerate(embeddings):
        embedding_lists.append(embedding.tolist())
        if (i + 1) % 50 == 0 or (i + 1) == len(embeddings):
            progress = (i + 1) / len(embeddings) * 100
            print(f"  Progress: {progress:.1f}% ({i + 1}/{len(embeddings)})")
    
    # Add embeddings to the dataframe
    print("Adding embeddings to dataframe...")
    df['name_embedding'] = embedding_lists
    
    # Save the enhanced CSV
    print(f"Saving embeddings to {output_path}...")
    df.to_csv(output_path, index=False)
    print("💾 File saved successfully!")
    
    print(f"✅ Success! Embedded {len(df)} topic names")
    print(f"📁 Output saved to: {output_path}")
    print(f"📊 Embedding dimensions: {embeddings.shape[1]}")
    
    return df, embeddings

def calculate_similarity(embedding1, embedding2):
    """Calculate cosine similarity between two embeddings"""
    return np.dot(embedding1, embedding2)

def find_similar_topics(df, query_topic_id, top_k=10):
    """
    Find topics most similar to the given topic ID
    
    Args:
        df: DataFrame with embeddings
        query_topic_id: ID of the topic to find similarities for
        top_k: Number of similar topics to return
    """
    
    # Find the query topic
    query_row = df[df['topicID'] == query_topic_id]
    if query_row.empty:
        print(f"Topic ID {query_topic_id} not found!")
        return
    
    query_embedding = np.array(query_row['name_embedding'].iloc[0])
    query_name = query_row['topicName'].iloc[0]
    
    # Calculate similarities with all other topics
    similarities = []
    for idx, row in df.iterrows():
        if row['topicID'] != query_topic_id:  # Skip self
            other_embedding = np.array(row['name_embedding'])
            similarity = calculate_similarity(query_embedding, other_embedding)
            similarities.append({
                'Id': row['topicID'],
                'Name': row['topicName'],
                'similarity': similarity
            })
    
    # Sort by similarity and return top K
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    
    print(f"\nTop {top_k} topics similar to '{query_name}' (ID: {query_topic_id}):")
    print("=" * 70)
    for i, sim in enumerate(similarities[:top_k], 1):
        print(f"{i:2d}. {sim['Name']} (ID: {sim['Id']}) - similarity: {sim['similarity']:.3f}")

def find_topics_by_keyword(df, keyword, top_k=10):
    """
    Find topics most similar to a given keyword/phrase
    
    Args:
        df: DataFrame with embeddings
        keyword: Text to search for similar topics
        top_k: Number of similar topics to return
    """
    
    # Load model to embed the keyword
    model = SentenceTransformer('all-MiniLM-L6-v2')
    keyword_embedding = model.encode([keyword], convert_to_numpy=True, normalize_embeddings=True)[0]
    
    # Calculate similarities with all topics
    similarities = []
    for idx, row in df.iterrows():
        topic_embedding = np.array(row['name_embedding'])
        similarity = calculate_similarity(keyword_embedding, topic_embedding)
        similarities.append({
            'Id': row['topicID'],
            'Name': row['topicName'],
            'similarity': similarity
        })
    
    # Sort by similarity and return top K
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    
    print(f"\nTop {top_k} topics similar to '{keyword}':")
    print("=" * 50)
    for i, sim in enumerate(similarities[:top_k], 1):
        print(f"{i:2d}. {sim['Name']} (ID: {sim['Id']}) - similarity: {sim['similarity']:.3f}")

if __name__ == "__main__":
    # Embed the topics
    df, embeddings = embed_topics()
    
    # Example usage
    if df is not None and len(df) > 0:
        # Find similar topics to the first topic
        first_topic_id = df['topicID'].iloc[0]
        first_topic_name = df['topicName'].iloc[0]
        print(f"\n🔍 Example 1: Finding topics similar to '{first_topic_name}' (ID: {first_topic_id})")
        find_similar_topics(df, first_topic_id)
        
        # Find topics by keyword
        print(f"\n🔍 Example 2: Finding topics similar to 'machine learning'")
        find_topics_by_keyword(df, "machine learning")