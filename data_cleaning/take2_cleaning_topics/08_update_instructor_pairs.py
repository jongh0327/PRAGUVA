"""
Script to update TopicInstructorPairs with the new topic IDs from splitting and merging.

This script:
1. Reads split_mapping.csv (original topics -> split topics)
2. Reads final_id_mapping.csv (merged duplicate IDs)
3. Updates TopicInstructorPairs_Deduplicated.csv with new IDs
4. Removes duplicate instructor pairs
"""

import csv
from collections import defaultdict

def load_mappings():
    """Load all ID mappings from split and merge operations."""
    id_map = {}  # old_id -> new_id
    
    # Load split mappings
    print("Loading split mappings...")
    try:
        with open('split_mapping.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                original_id = row['Original_ID']
                new_id = row['New_ID']
                # If this original ID was split, it now maps to multiple IDs
                # We'll handle this by creating instructor pairs for each split
                if original_id not in id_map:
                    id_map[original_id] = []
                id_map[original_id].append(new_id)
        print(f"  Loaded {len(id_map)} split topic mappings")
    except FileNotFoundError:
        print("  No split_mapping.csv found")
    
    # Load merge mappings (duplicates that were removed)
    print("Loading merge mappings...")
    merge_map = {}
    try:
        with open('final_id_mapping.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                old_id = row['Old_ID']
                new_id = row['New_ID']
                merge_map[old_id] = new_id
        print(f"  Loaded {len(merge_map)} merge mappings")
    except FileNotFoundError:
        print("  No final_id_mapping.csv found")
    
    # Load all valid topic IDs from TopicNode_Final.csv
    print("Loading valid topic IDs from TopicNode_Final.csv...")
    valid_ids = set()
    with open('TopicNode_Final.csv', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines[1:]:  # Skip header
            line = line.strip()
            if line:
                parts = line.split(',', 1)
                if len(parts) >= 1:
                    valid_ids.add(parts[0].strip())
    print(f"  Found {len(valid_ids)} valid topic IDs in final file")
    
    return id_map, merge_map, valid_ids

def update_instructor_pairs():
    """Update TopicInstructorPairs with new topic IDs."""
    input_file = 'TopicInstructorPairs_Deduplicated.csv'
    output_file = 'TopicInstructorPairs_Final.csv'
    
    # Load mappings
    split_map, merge_map, valid_ids = load_mappings()
    
    # Read instructor pairs
    print(f"\nReading {input_file}...")
    pairs = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        pairs = list(reader)
    
    print(f"  Original pairs: {len(pairs)}")
    
    # Update pairs
    updated_pairs = []
    skipped = 0
    
    for pair in pairs:
        topic_id = pair['TopicID']
        instructor_id = pair['InstructorID']
        
        # Check if this topic was split into multiple topics
        if topic_id in split_map:
            # Create pairs for each split topic
            for new_topic_id in split_map[topic_id]:
                # Check if this new ID was later merged
                final_id = merge_map.get(new_topic_id, new_topic_id)
                
                # Only add if the final ID exists in TopicNode_Final.csv
                if final_id in valid_ids:
                    updated_pairs.append({
                        'TopicID': final_id,
                        'InstructorID': instructor_id
                    })
                else:
                    skipped += 1
        else:
            # Topic wasn't split, but check if it was merged
            final_id = merge_map.get(topic_id, topic_id)
            
            # Only add if the final ID exists in TopicNode_Final.csv
            if final_id in valid_ids:
                updated_pairs.append({
                    'TopicID': final_id,
                    'InstructorID': instructor_id
                })
            else:
                skipped += 1
    
    print(f"  Updated pairs (before dedup): {len(updated_pairs)}")
    print(f"  Skipped (invalid IDs): {skipped}")
    
    # Remove duplicate pairs
    unique_pairs = []
    seen = set()
    
    for pair in updated_pairs:
        key = (pair['TopicID'], pair['InstructorID'])
        if key not in seen:
            seen.add(key)
            unique_pairs.append(pair)
    
    print(f"  Final unique pairs: {len(unique_pairs)}")
    print(f"  Duplicates removed: {len(updated_pairs) - len(unique_pairs)}")
    
    # Write output
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['TopicID', 'InstructorID'])
        writer.writeheader()
        writer.writerows(unique_pairs)
    
    print(f"\nOutput saved to {output_file}")
    
    # Verify all topic IDs exist
    print("\nVerifying all topic IDs exist in TopicNode_Final.csv...")
    missing_ids = set()
    for pair in unique_pairs:
        if pair['TopicID'] not in valid_ids:
            missing_ids.add(pair['TopicID'])
    
    if missing_ids:
        print(f"  WARNING: {len(missing_ids)} topic IDs not found in TopicNode_Final.csv:")
        for mid in sorted(missing_ids):
            print(f"    {mid}")
    else:
        print("  ✓ All topic IDs verified!")
    
    return unique_pairs

if __name__ == "__main__":
    print("=" * 80)
    print("UPDATING TOPIC-INSTRUCTOR PAIRS")
    print("=" * 80)
    
    updated_pairs = update_instructor_pairs()
    
    print("\n" + "=" * 80)
    print("COMPLETE!")
    print("=" * 80)
    print("\nSummary:")
    print(f"  - TopicNode_Final.csv: Source of truth for valid topic IDs")
    print(f"  - TopicInstructorPairs_Final.csv: Updated instructor relationships")
    print("\nAll topic IDs in the pairs file now match TopicNode_Final.csv")
