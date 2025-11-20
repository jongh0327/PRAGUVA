#!/usr/bin/env python3

import pandas as pd
import numpy as np
import os
import ast
from collections import defaultdict, deque

def load_embeddings_data(papers_csv="paper_summaries_with_embeddings.csv", 
                        topics_csv="topics_with_embeddings.csv"):
    """Load and prepare embedding data"""
    
    if not os.path.exists(papers_csv):
        print(f"Error: {papers_csv} not found!")
        return None, None
        
    if not os.path.exists(topics_csv):
        print(f"Error: {topics_csv} not found!")
        return None, None
    
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

def build_topic_hierarchy(hierarchy_csv="../../data/Edges/TopicParentPairs.csv"):
    """Build topic hierarchy from parent-child relationships"""
    
    if not os.path.exists(hierarchy_csv):
        print(f"Error: {hierarchy_csv} not found!")
        return None
    
    print("Loading topic hierarchy...")
    hierarchy_df = pd.read_csv(hierarchy_csv)
    
    # Build parent-child mappings
    child_to_parent = {}
    parent_to_children = defaultdict(list)
    
    for _, row in hierarchy_df.iterrows():
        child_id = row['childTopicID']
        parent_id = row['parentTopicID']
        
        child_to_parent[child_id] = parent_id
        parent_to_children[parent_id].append(child_id)
    
    print(f"Built hierarchy with {len(child_to_parent)} parent-child relationships")
    return child_to_parent, parent_to_children

def get_all_ancestors(topic_id, child_to_parent):
    """Get all ancestors of a topic (traversing up the hierarchy)"""
    ancestors = []
    current = topic_id
    
    # Traverse up the hierarchy until we reach a root (no parent)
    while current in child_to_parent:
        parent = child_to_parent[current]
        ancestors.append(parent)
        current = parent
    
    return ancestors

def find_top_k_similar_topics(paper_embedding, topics_df, k=3):
    """Find top K most similar topics for a paper"""
    similarities = []
    
    for _, topic_row in topics_df.iterrows():
        topic_embedding = topic_row['name_embedding']
        similarity = np.dot(paper_embedding, topic_embedding)
        
        similarities.append({
            'topicID': topic_row['topicID'],
            'topicName': topic_row['topicName'],
            'similarity': similarity
        })
    
    # Sort by similarity and return top K
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    return similarities[:k]

def generate_hierarchical_paper_topic_pairs(papers_csv="paper_summaries_with_embeddings.csv",
                                          topics_csv="topics_with_embeddings.csv", 
                                          hierarchy_csv="../../data/Edges/TopicParentPairs.csv",
                                          output_csv="HierarchicalPaperTopicPairs.csv",
                                          top_k=3):
    """
    Generate paper-topic pairs including hierarchical ancestors
    
    Args:
        papers_csv: CSV file with paper embeddings
        topics_csv: CSV file with topic embeddings  
        hierarchy_csv: CSV file with topic parent-child relationships
        output_csv: Output CSV filename
        top_k: Number of most similar topics to find per paper
    """
    
    # Load data
    papers_df, topics_df = load_embeddings_data(papers_csv, topics_csv)
    if papers_df is None or topics_df is None:
        return None
    
    child_to_parent, parent_to_children = build_topic_hierarchy(hierarchy_csv)
    if child_to_parent is None:
        return None
    
    # Create topic lookup for names
    topic_lookup = dict(zip(topics_df['topicID'], topics_df['topicName']))
    
    # Store all paper-topic relationships
    all_pairs = []
    total_papers = len(papers_df)
    
    print(f"Processing {total_papers} papers with top-{top_k} similarity + ancestors...")
    
    for paper_idx, paper_row in papers_df.iterrows():
        paper_id = paper_row['paperID']
        paper_embedding = paper_row['summary_embedding']
        paper_title = paper_row['paper_summary'].split(';')[0] if ';' in paper_row['paper_summary'] else paper_row['paper_summary'][:100]
        
        # Find top K most similar topics (child nodes)
        top_similar = find_top_k_similar_topics(paper_embedding, topics_df, top_k)
        
        # Collect all unique topic IDs (children + ancestors)
        all_related_topics = set()
        
        for similar_topic in top_similar:
            child_topic_id = similar_topic['topicID']
            child_similarity = similar_topic['similarity']
            
            # Add the child topic itself
            all_related_topics.add(child_topic_id)
            
            # Add direct relationship for child
            all_pairs.append({
                'paperID': paper_id,
                'topicID': child_topic_id,
                'topicName': similar_topic['topicName'],
                'paperTitle': paper_title,
                'relationship': 'direct',
                'similarity': child_similarity,
                'sourceChildTopic': child_topic_id
            })
            
            # Get all ancestors of this child topic
            ancestors = get_all_ancestors(child_topic_id, child_to_parent)
            
            for ancestor_id in ancestors:
                if ancestor_id not in all_related_topics:
                    all_related_topics.add(ancestor_id)
                    
                    # Add ancestor relationship
                    ancestor_name = topic_lookup.get(ancestor_id, f"Topic_{ancestor_id}")
                    all_pairs.append({
                        'paperID': paper_id,
                        'topicID': ancestor_id,
                        'topicName': ancestor_name,
                        'paperTitle': paper_title,
                        'relationship': 'ancestor',
                        'similarity': child_similarity,  # Inherit similarity from child
                        'sourceChildTopic': child_topic_id
                    })
        
        # Progress tracking
        if (paper_idx + 1) % 50 == 0 or (paper_idx + 1) == total_papers:
            progress = (paper_idx + 1) / total_papers * 100
            pairs_count = len(all_pairs)
            avg_topics_per_paper = pairs_count / (paper_idx + 1)
            print(f"  Progress: {progress:.1f}% ({paper_idx + 1}/{total_papers}) - {pairs_count:,} total pairs, avg {avg_topics_per_paper:.1f} topics/paper")
    
    # Convert to DataFrame and save
    if all_pairs:
        pairs_df = pd.DataFrame(all_pairs)
        
        # Sort by paperID, then by relationship (direct first), then by similarity
        pairs_df = pairs_df.sort_values(['paperID', 'relationship', 'similarity'], 
                                       ascending=[True, True, False])
        
        # Save to CSV
        pairs_df.to_csv(output_csv, index=False)
        
        print(f"\n✅ Success! Generated {len(pairs_df):,} hierarchical paper-topic pairs")
        print(f"📁 Output saved to: {output_csv}")
        
        # Statistics
        unique_papers = pairs_df['paperID'].nunique()
        unique_topics = pairs_df['topicID'].nunique()
        direct_pairs = len(pairs_df[pairs_df['relationship'] == 'direct'])
        ancestor_pairs = len(pairs_df[pairs_df['relationship'] == 'ancestor'])
        
        print(f"\n📊 Statistics:")
        print(f"  - Papers processed: {unique_papers:,}")
        print(f"  - Unique topics involved: {unique_topics:,}")
        print(f"  - Direct relationships: {direct_pairs:,}")
        print(f"  - Ancestor relationships: {ancestor_pairs:,}")
        print(f"  - Average topics per paper: {len(pairs_df) / unique_papers:.1f}")
        
        # Show sample results
        print(f"\n🔝 Sample results for first paper:")
        first_paper_pairs = pairs_df[pairs_df['paperID'] == pairs_df['paperID'].iloc[0]]
        print(first_paper_pairs[['topicID', 'topicName', 'relationship', 'similarity']].head(10).to_string(index=False))
        
        return pairs_df
    else:
        print("No pairs generated!")
        return None

def analyze_hierarchical_coverage(pairs_csv="HierarchicalPaperTopicPairs.csv"):
    """Analyze the hierarchical coverage of paper-topic relationships"""
    
    if not os.path.exists(pairs_csv):
        print(f"Error: {pairs_csv} not found!")
        return
    
    pairs_df = pd.read_csv(pairs_csv)
    
    print(f"📊 Hierarchical Coverage Analysis:")
    print(f"  Total relationships: {len(pairs_df):,}")
    
    # Breakdown by relationship type
    relationship_counts = pairs_df['relationship'].value_counts()
    print(f"\n📈 Relationship Types:")
    for rel_type, count in relationship_counts.items():
        percentage = count / len(pairs_df) * 100
        print(f"  - {rel_type.title()}: {count:,} ({percentage:.1f}%)")
    
    # Papers with most total topics (direct + ancestors)
    paper_topic_counts = pairs_df.groupby('paperID').size().sort_values(ascending=False)
    print(f"\n📄 Papers with most topic relationships:")
    for paper_id, count in paper_topic_counts.head(5).items():
        paper_title = pairs_df[pairs_df['paperID'] == paper_id]['paperTitle'].iloc[0][:60]
        print(f"  Paper {paper_id}: {count} topics - {paper_title}...")
    
    # Most connected topics
    topic_paper_counts = pairs_df.groupby('topicID').size().sort_values(ascending=False)
    print(f"\n🏷️  Most connected topics:")
    for topic_id, count in topic_paper_counts.head(5).items():
        topic_name = pairs_df[pairs_df['topicID'] == topic_id]['topicName'].iloc[0]
        print(f"  Topic {topic_id}: {count} papers - {topic_name}")

if __name__ == "__main__":
    # Generate hierarchical paper-topic pairs
    pairs_df = generate_hierarchical_paper_topic_pairs(top_k=3)
    
    if pairs_df is not None:
        print(f"\n🔍 Running hierarchical coverage analysis...")
        analyze_hierarchical_coverage()