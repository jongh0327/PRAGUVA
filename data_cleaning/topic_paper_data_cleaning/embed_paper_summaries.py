#!/usr/bin/env python3

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import os

def embed_paper_summaries(csv_path="paper_summary.csv", output_path="paper_summaries_with_embeddings.csv"):
    """
    Embed paper summaries from CSV and save embeddings alongside the data.
    
    Args:
        csv_path: Path to the paper_summary.csv file
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
    
    print(f"Found {len(df)} papers to embed")
    
    # Check if paper_summary column exists
    if 'paper_summary' not in df.columns:
        print("Error: 'paper_summary' column not found in CSV!")
        print(f"Available columns: {list(df.columns)}")
        return
    
    # Extract texts to embed (the paper summaries)
    texts = df['paper_summary'].fillna('').tolist()
    
    # Generate embeddings with progress tracking
    print("Generating embeddings...")
    print(f"Processing {len(texts)} paper summaries...")
    
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
        if (i + 1) % 10 == 0 or (i + 1) == len(embeddings):
            progress = (i + 1) / len(embeddings) * 100
            print(f"  Progress: {progress:.1f}% ({i + 1}/{len(embeddings)})")
    
    # Add embeddings to the dataframe
    print("Adding embeddings to dataframe...")
    df['summary_embedding'] = embedding_lists
    
    # Save the enhanced CSV
    print(f"Saving embeddings to {output_path}...")
    df.to_csv(output_path, index=False)
    print("💾 File saved successfully!")
    
    print(f"✅ Success! Embedded {len(df)} paper summaries")
    print(f"📁 Output saved to: {output_path}")
    print(f"📊 Embedding dimensions: {embeddings.shape[1]}")
    
    return df, embeddings

def calculate_similarity(embedding1, embedding2):
    """Calculate cosine similarity between two embeddings"""
    return np.dot(embedding1, embedding2)

def find_similar_papers(df, query_paper_id, top_k=5):
    """
    Find papers most similar to the given paper ID
    
    Args:
        df: DataFrame with embeddings
        query_paper_id: ID of the paper to find similarities for
        top_k: Number of similar papers to return
    """
    
    # Find the query paper
    query_row = df[df['paperID'] == query_paper_id]
    if query_row.empty:
        print(f"Paper ID {query_paper_id} not found!")
        return
    
    query_embedding = np.array(query_row['summary_embedding'].iloc[0])
    
    # Calculate similarities with all other papers
    similarities = []
    for idx, row in df.iterrows():
        if row['paperID'] != query_paper_id:  # Skip self
            other_embedding = np.array(row['summary_embedding'])
            similarity = calculate_similarity(query_embedding, other_embedding)
            similarities.append({
                'paperID': row['paperID'],
                'similarity': similarity,
                'summary': row['paper_summary'][:100] + "..."  # First 100 chars
            })
    
    # Sort by similarity and return top K
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    
    print(f"\nTop {top_k} papers similar to {query_paper_id}:")
    print("=" * 60)
    for i, sim in enumerate(similarities[:top_k], 1):
        print(f"{i}. Paper {sim['paperID']} (similarity: {sim['similarity']:.3f})")
        print(f"   {sim['summary']}")
        print()

if __name__ == "__main__":
    # Embed the paper summaries
    df, embeddings = embed_paper_summaries()
    
    # Example usage: find papers similar to the first paper
    if df is not None and len(df) > 0:
        first_paper_id = df['paperID'].iloc[0]
        print(f"\n🔍 Example: Finding papers similar to {first_paper_id}")
        find_similar_papers(df, first_paper_id)