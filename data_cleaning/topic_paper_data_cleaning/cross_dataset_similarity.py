#!/usr/bin/env python3

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import ast

def cross_dataset_similarity(papers_csv="paper_summaries_with_embeddings.csv", 
                           topics_csv="topics_with_embeddings.csv"):
    """
    Find similarities between papers and topics across datasets
    
    Args:
        papers_csv: CSV file with paper embeddings
        topics_csv: CSV file with topic embeddings
    """
    
    # Check if files exist
    if not os.path.exists(papers_csv):
        print(f"Error: {papers_csv} not found! Run embed_paper_summaries.py first.")
        return
        
    if not os.path.exists(topics_csv):
        print(f"Error: {topics_csv} not found! Run embed_topics.py first.")
        return
    
    # Load both datasets
    print("Loading datasets...")
    papers_df = pd.read_csv(papers_csv)
    topics_df = pd.read_csv(topics_csv)
    
    # Convert string representations back to numpy arrays
    print("Converting embeddings from strings to arrays...")
    papers_df['summary_embedding'] = papers_df['summary_embedding'].apply(
        lambda x: np.array(ast.literal_eval(x)) if isinstance(x, str) else x
    )
    topics_df['name_embedding'] = topics_df['name_embedding'].apply(
        lambda x: np.array(ast.literal_eval(x)) if isinstance(x, str) else x
    )
    
    print(f"Loaded {len(papers_df)} papers and {len(topics_df)} topics")
    
    return papers_df, topics_df

def find_papers_for_topic(papers_df, topics_df, topic_id, top_k=5):
    """
    Find papers most relevant to a specific topic
    
    Args:
        papers_df: DataFrame with paper embeddings
        topics_df: DataFrame with topic embeddings
        topic_id: ID of the topic to find papers for
        top_k: Number of papers to return
    """
    
    # Find the topic
    topic_row = topics_df[topics_df['Id'] == topic_id]
    if topic_row.empty:
        print(f"Topic ID {topic_id} not found!")
        return
    
    topic_embedding = topic_row['name_embedding'].iloc[0]
    topic_name = topic_row['Name'].iloc[0]
    
    # Calculate similarities with all papers
    print(f"Calculating similarities with {len(papers_df)} papers...")
    similarities = []
    for idx, row in papers_df.iterrows():
        paper_embedding = row['summary_embedding']
        similarity = np.dot(topic_embedding, paper_embedding)
        similarities.append({
            'paperID': row['paperID'],
            'similarity': similarity,
            'summary': row['paper_summary'][:150] + "..."  # First 150 chars
        })
        
        # Show progress every 10 papers or at the end
        if (idx + 1) % 10 == 0 or (idx + 1) == len(papers_df):
            progress = (idx + 1) / len(papers_df) * 100
            print(f"  Progress: {progress:.1f}% ({idx + 1}/{len(papers_df)})")
    
    # Sort by similarity and return top K
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    
    print(f"\nTop {top_k} papers most relevant to topic '{topic_name}' (ID: {topic_id}):")
    print("=" * 80)
    for i, sim in enumerate(similarities[:top_k], 1):
        print(f"{i}. Paper {sim['paperID']} (similarity: {sim['similarity']:.3f})")
        print(f"   {sim['summary']}")
        print()

def find_topics_for_paper(papers_df, topics_df, paper_id, top_k=10):
    """
    Find topics most relevant to a specific paper
    
    Args:
        papers_df: DataFrame with paper embeddings
        topics_df: DataFrame with topic embeddings
        paper_id: ID of the paper to find topics for
        top_k: Number of topics to return
    """
    
    # Find the paper
    paper_row = papers_df[papers_df['paperID'] == paper_id]
    if paper_row.empty:
        print(f"Paper ID {paper_id} not found!")
        return
    
    paper_embedding = paper_row['summary_embedding'].iloc[0]
    paper_summary = paper_row['paper_summary'].iloc[0]
    
    # Calculate similarities with all topics
    print(f"Calculating similarities with {len(topics_df)} topics...")
    similarities = []
    for idx, row in topics_df.iterrows():
        topic_embedding = row['name_embedding']
        similarity = np.dot(paper_embedding, topic_embedding)
        similarities.append({
            'Id': row['Id'],
            'Name': row['Name'],
            'similarity': similarity
        })
        
        # Show progress every 50 topics or at the end
        if (idx + 1) % 50 == 0 or (idx + 1) == len(topics_df):
            progress = (idx + 1) / len(topics_df) * 100
            print(f"  Progress: {progress:.1f}% ({idx + 1}/{len(topics_df)})")
    
    # Sort by similarity and return top K
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    
    print(f"\nTop {top_k} topics most relevant to paper {paper_id}:")
    print(f"Paper summary: {paper_summary[:200]}...")
    print("=" * 60)
    for i, sim in enumerate(similarities[:top_k], 1):
        print(f"{i:2d}. {sim['Name']} (ID: {sim['Id']}) - similarity: {sim['similarity']:.3f}")

def recommend_papers_by_topic_name(papers_df, topics_df, topic_name_query, top_papers=5):
    """
    Find papers related to a topic name (fuzzy matching + semantic similarity)
    
    Args:
        papers_df: DataFrame with paper embeddings
        topics_df: DataFrame with topic embeddings
        topic_name_query: Name or partial name of topic to search for
        top_papers: Number of papers to recommend
    """
    
    # Find topics that match the query (case-insensitive partial match)
    matching_topics = topics_df[topics_df['Name'].str.contains(topic_name_query, case=False, na=False)]
    
    if matching_topics.empty:
        print(f"No topics found matching '{topic_name_query}'")
        return
    
    print(f"Found {len(matching_topics)} topics matching '{topic_name_query}':")
    for _, topic in matching_topics.iterrows():
        print(f"  - {topic['Name']} (ID: {topic['Id']})")
    
    # Use the first matching topic for paper recommendations
    best_topic = matching_topics.iloc[0]
    print(f"\nUsing topic: '{best_topic['Name']}' for paper recommendations...")
    
    find_papers_for_topic(papers_df, topics_df, best_topic['Id'], top_papers)

if __name__ == "__main__":
    # Load both datasets
    papers_df, topics_df = cross_dataset_similarity()
    
    if papers_df is not None and topics_df is not None:
        # Example 1: Find papers for a specific topic
        if len(topics_df) > 0:
            first_topic_id = topics_df['Id'].iloc[0]
            print("🔍 Example 1: Finding papers for the first topic")
            find_papers_for_topic(papers_df, topics_df, first_topic_id)
        
        # Example 2: Find topics for a specific paper
        if len(papers_df) > 0:
            first_paper_id = papers_df['paperID'].iloc[0]
            print(f"\n🔍 Example 2: Finding topics for paper {first_paper_id}")
            find_topics_for_paper(papers_df, topics_df, first_paper_id)
        
        # Example 3: Recommend papers by topic name
        print(f"\n🔍 Example 3: Finding papers related to 'machine learning'")
        recommend_papers_by_topic_name(papers_df, topics_df, "machine learning")