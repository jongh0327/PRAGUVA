#!/usr/bin/env python3

import pandas as pd
import numpy as np
import os
import ast

def generate_paper_topic_pairs(papers_csv="paper_summaries_with_embeddings.csv", 
                              topics_csv="topics_with_embeddings.csv",
                              output_csv="PaperTopicPairs.csv",
                              similarity_threshold=0.4):
    """
    Generate paper-topic pairs based on embedding similarity threshold
    
    Args:
        papers_csv: CSV file with paper embeddings
        topics_csv: CSV file with topic embeddings
        output_csv: Output CSV filename for paper-topic pairs
        similarity_threshold: Minimum similarity score to create a pair (0.0 to 1.0)
    """
    
    # Check if input files exist
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
    print(f"Similarity threshold: {similarity_threshold}")
    
    # Store all paper-topic pairs that meet the threshold
    paper_topic_pairs = []
    total_comparisons = len(papers_df) * len(topics_df)
    processed_comparisons = 0
    
    print(f"Processing {total_comparisons:,} paper-topic comparisons...")
    
    # For each paper, compare with all topics
    for paper_idx, paper_row in papers_df.iterrows():
        paper_id = paper_row['paperID']
        paper_embedding = paper_row['summary_embedding']
        
        # Calculate similarities with all topics for this paper
        for topic_idx, topic_row in topics_df.iterrows():
            topic_id = topic_row['topicID']
            topic_embedding = topic_row['name_embedding']
            
            # Calculate cosine similarity
            similarity = np.dot(paper_embedding, topic_embedding)
            
            # If similarity meets threshold, add to pairs
            if similarity >= similarity_threshold:
                # Extract topic name and paper title
                topic_name = topic_row['topicName']
                paper_title = paper_row['paper_summary'].split(';')[0] if ';' in paper_row['paper_summary'] else paper_row['paper_summary'][:100]
                
                paper_topic_pairs.append({
                    'paperID': paper_id,
                    'topicID': topic_id,
                    'similarity': similarity,
                    'topicName': topic_name,
                    'paperTitle': paper_title
                })
            
            processed_comparisons += 1
            
            # Show progress every 10,000 comparisons
            if processed_comparisons % 10000 == 0 or processed_comparisons == total_comparisons:
                progress = processed_comparisons / total_comparisons * 100
                pairs_found = len(paper_topic_pairs)
                print(f"  Progress: {progress:.1f}% ({processed_comparisons:,}/{total_comparisons:,}) - {pairs_found:,} pairs found")
        
        # Show progress every 50 papers
        if (paper_idx + 1) % 50 == 0:
            papers_progress = (paper_idx + 1) / len(papers_df) * 100
            pairs_found = len(paper_topic_pairs)
            print(f"  Papers processed: {papers_progress:.1f}% ({paper_idx + 1}/{len(papers_df)}) - {pairs_found:,} pairs found so far")
    
    # Convert to DataFrame and save
    if paper_topic_pairs:
        pairs_df = pd.DataFrame(paper_topic_pairs)
        
        # Sort by paperID, then by similarity (descending)
        pairs_df = pairs_df.sort_values(['paperID', 'similarity'], ascending=[True, False])
        
        # Reorder columns to match requested format
        pairs_df = pairs_df[['paperID', 'topicID', 'similarity', 'topicName', 'paperTitle']]
        
        # Save to CSV
        pairs_df.to_csv(output_csv, index=False)
        
        print(f"\n✅ Success! Generated {len(pairs_df):,} paper-topic pairs")
        print(f"📁 Output saved to: {output_csv}")
        print(f"🎯 Similarity threshold: {similarity_threshold}")
        
        # Show some statistics
        unique_papers = pairs_df['paperID'].nunique()
        unique_topics = pairs_df['topicID'].nunique()
        avg_topics_per_paper = len(pairs_df) / unique_papers if unique_papers > 0 else 0
        avg_papers_per_topic = len(pairs_df) / unique_topics if unique_topics > 0 else 0
        
        print(f"\n📊 Statistics:")
        print(f"  - Papers with topic matches: {unique_papers:,} / {len(papers_df):,} ({unique_papers/len(papers_df)*100:.1f}%)")
        print(f"  - Topics with paper matches: {unique_topics:,} / {len(topics_df):,} ({unique_topics/len(topics_df)*100:.1f}%)")
        print(f"  - Average topics per paper: {avg_topics_per_paper:.1f}")
        print(f"  - Average papers per topic: {avg_papers_per_topic:.1f}")
        print(f"  - Similarity score range: {pairs_df['similarity'].min():.3f} to {pairs_df['similarity'].max():.3f}")
        
        # Show top 10 pairs
        print(f"\n🔝 Top 10 paper-topic pairs by similarity:")
        print(pairs_df.head(10).to_string(index=False))
        
        return pairs_df
    else:
        print(f"\n⚠️  No paper-topic pairs found with similarity >= {similarity_threshold}")
        print("Consider lowering the threshold or checking your embeddings.")
        return None

def analyze_paper_topics(pairs_csv="PaperTopicPairs.csv", papers_csv="paper_summaries_with_embeddings.csv", topics_csv="topics_with_embeddings.csv"):
    """
    Analyze the generated paper-topic pairs
    """
    
    if not os.path.exists(pairs_csv):
        print(f"Error: {pairs_csv} not found! Run generate_paper_topic_pairs first.")
        return
    
    pairs_df = pd.read_csv(pairs_csv)
    papers_df = pd.read_csv(papers_csv)
    topics_df = pd.read_csv(topics_csv)
    
    print(f"📊 Analysis of {pairs_csv}:")
    print(f"  Total pairs: {len(pairs_df):,}")
    
    # Find papers with most topics
    paper_topic_counts = pairs_df.groupby('paperID').size().sort_values(ascending=False)
    print(f"\n📄 Papers with most topics:")
    for paper_id, count in paper_topic_counts.head(5).items():
        paper_title = papers_df[papers_df['paperID'] == paper_id]['paper_summary'].iloc[0][:100]
        print(f"  Paper {paper_id}: {count} topics - {paper_title}...")
    
    # Find topics with most papers
    topic_paper_counts = pairs_df.groupby('topicID').size().sort_values(ascending=False)
    print(f"\n🏷️  Topics with most papers:")
    for topic_id, count in topic_paper_counts.head(5).items():
        topic_name = topics_df[topics_df['topicID'] == topic_id]['topicName'].iloc[0]
        print(f"  Topic {topic_id}: {count} papers - {topic_name}")

if __name__ == "__main__":
    # Generate paper-topic pairs with 0.60 threshold
    pairs_df = generate_paper_topic_pairs(similarity_threshold=0.60)
    
    if pairs_df is not None:
        print(f"\n🔍 Running analysis...")
        analyze_paper_topics()