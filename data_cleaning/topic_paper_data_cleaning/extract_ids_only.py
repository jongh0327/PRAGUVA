#!/usr/bin/env python3

import pandas as pd

def extract_paper_topic_ids(input_csv="HierarchicalPaperTopicPairs.csv", 
                           output_csv="PaperTopicPairs_IDs_Only.csv"):
    """
    Extract only paperID and topicID columns from hierarchical pairs
    
    Args:
        input_csv: Input CSV with all hierarchical data
        output_csv: Output CSV with only paperID and topicID
    """
    
    print(f"Reading {input_csv}...")
    df = pd.read_csv(input_csv)
    
    print(f"Found {len(df):,} total relationships")
    
    # Select only paperID and topicID columns
    df_ids = df[['paperID', 'topicID']]
    
    # Save to new CSV
    df_ids.to_csv(output_csv, index=False)
    
    print(f"✅ Extracted {len(df_ids):,} paper-topic pairs")
    print(f"📁 Saved to: {output_csv}")
    
    # Show statistics
    unique_papers = df_ids['paperID'].nunique()
    unique_topics = df_ids['topicID'].nunique()
    
    print(f"\n📊 Statistics:")
    print(f"  - Unique papers: {unique_papers:,}")
    print(f"  - Unique topics: {unique_topics:,}")
    print(f"  - Total pairs: {len(df_ids):,}")

if __name__ == "__main__":
    extract_paper_topic_ids()
