#!/usr/bin/env python3
"""
Script to convert hierarchical TopicNode_Ultima.csv into:
1. TopicNode.csv - Flat list of all topics (topicID, topicName)
2. TopicParentPairs.csv - Parent-child relationships (childTopicID, parentTopicID)
"""

import csv
import os
from collections import defaultdict

# File paths
INPUT_FILE = 'TopicNode_Ultima_Fixed.csv'  # Use the fixed version
OUTPUT_TOPIC_NODE = 'TopicNode.csv'
OUTPUT_PARENT_PAIRS = 'TopicParentPairs.csv'

def main():
    # Store all unique topics with their IDs
    # Key: topic name, Value: topic ID
    topic_id_map = {}
    
    # Store parent-child relationships as a set to avoid duplicates
    # Set of tuples: (child_id, parent_id)
    parent_pairs_set = set()
    
    # Counter for generating new IDs for hierarchy nodes
    # Start after the max leaf node ID
    next_id = 10000  # High number to avoid conflicts
    
    print("Reading TopicNode_Ultima.csv...")
    
    # First pass: collect all leaf topics with their existing IDs
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            leaf_id = row['TopicID']
            leaf_name = row['TopicName']
            # Only add if not already present (shouldn't happen for leaf nodes)
            if leaf_name not in topic_id_map:
                topic_id_map[leaf_name] = leaf_id
    
    print(f"✓ Found {len(topic_id_map)} leaf topics")
    
    # Second pass: build hierarchy and assign IDs to parent nodes
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            leaf_id = row['TopicID']
            leaf_name = row['TopicName']
            
            # Build the hierarchy chain from Level1 -> Level2 -> Level3 -> Level4 -> Leaf
            hierarchy = []
            
            for level_col in ['Level1_Category', 'Level2_Category', 'Level3_Category', 'Level4_Category']:
                level_value = row.get(level_col)
                if level_value:
                    level_name = level_value.strip()
                    if level_name and level_name not in ['', 'None']:
                        # Only add to hierarchy if it's unique in the current chain
                        if not hierarchy or hierarchy[-1] != level_name:
                            hierarchy.append(level_name)
            
            # Add the leaf node to the hierarchy
            hierarchy.append(leaf_name)
            
            # Assign IDs to hierarchy parent nodes (categories)
            for category_name in hierarchy[:-1]:  # Exclude leaf node
                if category_name not in topic_id_map:
                    topic_id_map[category_name] = str(next_id)
                    next_id += 1
            
            # Create parent-child pairs
            for i in range(len(hierarchy) - 1):
                parent_name = hierarchy[i]
                child_name = hierarchy[i + 1]
                
                # Skip if parent and child are the same (shouldn't happen, but safety check)
                if parent_name == child_name:
                    continue
                
                # Get IDs
                parent_id = topic_id_map[parent_name]
                child_id = topic_id_map[child_name]
                
                # Skip if parent and child IDs are the same
                if parent_id == child_id:
                    continue
                
                # Add parent-child relationship (set automatically handles duplicates)
                parent_pairs_set.add((child_id, parent_id))
    
    print(f"✓ Total unique topics (leaf + categories): {len(topic_id_map)}")
    print(f"✓ Found {len(parent_pairs_set)} unique parent-child relationships")
    
    # Write TopicNode.csv
    print(f"\nWriting {OUTPUT_TOPIC_NODE}...")
    with open(OUTPUT_TOPIC_NODE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['TopicID', 'TopicName'])
        
        # Sort by ID
        sorted_topics = sorted(topic_id_map.items(), key=lambda x: int(x[1]))
        for topic_name, topic_id in sorted_topics:
            writer.writerow([topic_id, topic_name])
    
    print(f"✓ Wrote {len(topic_id_map)} topics to {OUTPUT_TOPIC_NODE}")
    
    # Write TopicParentPairs.csv
    print(f"\nWriting {OUTPUT_PARENT_PAIRS}...")
    with open(OUTPUT_PARENT_PAIRS, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ChildTopicID', 'ParentTopicID'])
        
        # Sort by child ID
        sorted_pairs = sorted(parent_pairs_set, key=lambda x: int(x[0]))
        for child_id, parent_id in sorted_pairs:
            writer.writerow([child_id, parent_id])
    
    print(f"✓ Wrote {len(parent_pairs_set)} parent-child pairs to {OUTPUT_PARENT_PAIRS}")
    
    print("\n✅ Conversion complete!")
    print(f"\nNext steps:")
    print(f"1. Review {OUTPUT_TOPIC_NODE}")
    print(f"2. Review {OUTPUT_PARENT_PAIRS}")
    print(f"3. Create InstructorTopicPairs.csv using these new IDs")

if __name__ == "__main__":
    main()
