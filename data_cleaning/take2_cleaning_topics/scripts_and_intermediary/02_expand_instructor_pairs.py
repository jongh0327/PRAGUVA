#!/usr/bin/env python3
"""
Script to expand InstructorTopicPairs to include all ancestor topics in the hierarchy.

Reads:
- TopicNode.csv (all topics)
- TopicParentPairs.csv (parent-child relationships)
- TopicInstructorPairs_Final.csv (current leaf-only pairs)

Outputs:
- InstructorTopicPairs.csv (expanded with all ancestors)
"""

import csv
from collections import defaultdict

# File paths
TOPIC_NODE_FILE = 'TopicNode.csv'
PARENT_PAIRS_FILE = 'TopicParentPairs.csv'
INPUT_INSTRUCTOR_PAIRS = 'TopicInstructorPairs_Final.csv'
OUTPUT_INSTRUCTOR_PAIRS = 'InstructorTopicPairs.csv'

def build_parent_lookup():
    """
    Build a dictionary mapping child_id -> parent_id
    Returns: dict where key=child_id, value=parent_id
    """
    parent_lookup = {}
    
    print("Reading TopicParentPairs.csv...")
    with open(PARENT_PAIRS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            child_id = row['ChildTopicID']
            parent_id = row['ParentTopicID']
            parent_lookup[child_id] = parent_id
    
    print(f"✓ Loaded {len(parent_lookup)} parent-child relationships")
    return parent_lookup

def get_all_ancestors(topic_id, parent_lookup):
    """
    Trace up the hierarchy tree to find all ancestor topic IDs.
    
    Args:
        topic_id: The starting topic ID
        parent_lookup: Dictionary mapping child_id -> parent_id
    
    Returns:
        List of ancestor topic IDs (not including the original topic_id)
    """
    ancestors = []
    current_id = topic_id
    visited = set()  # Track visited nodes to detect cycles
    
    # Traverse up the tree
    while current_id in parent_lookup:
        # Cycle detection - if we've seen this node before, stop
        if current_id in visited:
            print(f"⚠️  Warning: Circular reference detected for topic {topic_id}")
            break
        
        visited.add(current_id)
        parent_id = parent_lookup[current_id]
        ancestors.append(parent_id)
        current_id = parent_id
    
    return ancestors

def expand_instructor_pairs(parent_lookup):
    """
    Read instructor-topic pairs and expand to include all ancestors.
    """
    # Set to store all pairs (instructor_id, topic_id)
    all_pairs = set()
    
    print(f"\nReading {INPUT_INSTRUCTOR_PAIRS}...")
    pairs_read = 0
    
    with open(INPUT_INSTRUCTOR_PAIRS, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            pairs_read += 1
            instructor_id = row['InstructorID']
            topic_id = row['TopicID']
            
            # Add the original pair (leaf node)
            all_pairs.add((instructor_id, topic_id))
            
            # Find all ancestors and add pairs for each
            ancestors = get_all_ancestors(topic_id, parent_lookup)
            for ancestor_id in ancestors:
                all_pairs.add((instructor_id, ancestor_id))
    
    print(f"✓ Read {pairs_read} original instructor-topic pairs")
    print(f"✓ Expanded to {len(all_pairs)} total pairs (including ancestors)")
    
    return all_pairs

def write_expanded_pairs(all_pairs):
    """
    Write expanded instructor-topic pairs to output file.
    """
    print(f"\nWriting {OUTPUT_INSTRUCTOR_PAIRS}...")
    
    # Sort pairs by instructor_id, then topic_id
    sorted_pairs = sorted(all_pairs, key=lambda x: (int(x[0]), int(x[1])))
    
    with open(OUTPUT_INSTRUCTOR_PAIRS, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['InstructorID', 'TopicID'])
        
        for instructor_id, topic_id in sorted_pairs:
            writer.writerow([instructor_id, topic_id])
    
    print(f"✓ Wrote {len(sorted_pairs)} instructor-topic pairs to {OUTPUT_INSTRUCTOR_PAIRS}")

def main():
    print("=" * 60)
    print("Expanding InstructorTopicPairs with Ancestor Topics")
    print("=" * 60)
    
    # Step 1: Build parent lookup
    parent_lookup = build_parent_lookup()
    
    # Step 2: Expand instructor pairs
    all_pairs = expand_instructor_pairs(parent_lookup)
    
    # Step 3: Write output
    write_expanded_pairs(all_pairs)
    
    print("\n✅ Expansion complete!")
    print(f"\nOutput file: {OUTPUT_INSTRUCTOR_PAIRS}")
    
    # Show some statistics
    original_count = sum(1 for _ in open(INPUT_INSTRUCTOR_PAIRS)) - 1  # -1 for header
    expansion_factor = len(all_pairs) / original_count if original_count > 0 else 0
    print(f"\nStatistics:")
    print(f"  Original pairs: {original_count}")
    print(f"  Expanded pairs: {len(all_pairs)}")
    print(f"  Expansion factor: {expansion_factor:.2f}x")

if __name__ == "__main__":
    main()
