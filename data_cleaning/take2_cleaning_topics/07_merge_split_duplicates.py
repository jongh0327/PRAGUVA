"""
Script to merge duplicates found in split_duplicates_report.txt
"""

import csv
import re

def parse_duplicate_report():
    """Parse the split_duplicates_report.txt to extract exact duplicates."""
    report_file = 'split_duplicates_report.txt'
    exact_duplicates = []
    fuzzy_duplicates = []
    
    with open(report_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    section = None
    current_group = []
    
    for line in lines:
        if 'EXACT DUPLICATES:' in line:
            section = 'exact'
            continue
        elif 'FUZZY DUPLICATES' in line:
            section = 'fuzzy'
            continue
        
        # Parse exact duplicate groups
        if section == 'exact':
            if line.startswith('Duplicate Group'):
                if current_group:
                    exact_duplicates.append(current_group)
                current_group = []
            elif line.strip().startswith('ID '):
                match = re.match(r'\s*ID (\d+): (.+)', line)
                if match:
                    topic_id = match.group(1)
                    topic_name = match.group(2).strip()
                    current_group.append((topic_id, topic_name))
        
        # Parse fuzzy duplicates
        elif section == 'fuzzy':
            if line.startswith('Similarity:'):
                if current_group:
                    fuzzy_duplicates.append(current_group)
                current_group = []
            elif line.strip().startswith('ID '):
                match = re.match(r'\s*ID (\d+): (.+)', line)
                if match:
                    topic_id = match.group(1)
                    topic_name = match.group(2).strip()
                    current_group.append((topic_id, topic_name))
    
    # Add last groups
    if section == 'exact' and current_group:
        exact_duplicates.append(current_group)
    elif section == 'fuzzy' and current_group:
        fuzzy_duplicates.append(current_group)
    
    return exact_duplicates, fuzzy_duplicates

def create_merge_map(exact_duplicates, fuzzy_duplicates, fuzzy_decisions_file='fuzzy_merge_decisions.txt'):
    """Create a mapping of IDs to merge (old_id -> keep_id)."""
    merge_map = {}
    
    # Process exact duplicates - always merge, keep lowest ID
    print("Processing exact duplicates...")
    for group in exact_duplicates:
        if len(group) < 2:
            continue
        # Sort by ID (numeric)
        sorted_group = sorted(group, key=lambda x: int(x[0]))
        keep_id = sorted_group[0][0]
        keep_name = sorted_group[0][1]
        
        print(f"  Merging group (keeping ID {keep_id}: {keep_name}):")
        for topic_id, topic_name in sorted_group[1:]:
            print(f"    Merge ID {topic_id}: {topic_name} -> {keep_id}")
            merge_map[topic_id] = keep_id
    
    # Process fuzzy duplicates - only merge if decision file exists
    print("\nProcessing fuzzy duplicates...")
    try:
        with open(fuzzy_decisions_file, 'r', encoding='utf-8') as f:
            fuzzy_merge_ids = set()
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Format: "ID1,ID2" means merge ID2 into ID1
                    parts = line.split(',')
                    if len(parts) == 2:
                        keep_id = parts[0].strip()
                        merge_id = parts[1].strip()
                        merge_map[merge_id] = keep_id
                        fuzzy_merge_ids.add((keep_id, merge_id))
        
        print(f"  Applied {len(fuzzy_merge_ids)} fuzzy merge decisions")
    except FileNotFoundError:
        print(f"  No fuzzy merge decisions file found - skipping fuzzy merges")
        print(f"  Create '{fuzzy_decisions_file}' with format: keep_id,merge_id")
    
    return merge_map

def merge_duplicates():
    """Merge duplicate topics in TopicNode_Split.csv."""
    input_file = 'TopicNode_Split.csv'
    output_file = 'TopicNode_Final.csv'
    mapping_file = 'final_id_mapping.csv'
    
    # Parse duplicate report
    exact_duplicates, fuzzy_duplicates = parse_duplicate_report()
    
    print(f"Found {len(exact_duplicates)} exact duplicate groups")
    print(f"Found {len(fuzzy_duplicates)} fuzzy duplicate pairs\n")
    
    # Create merge map
    merge_map = create_merge_map(exact_duplicates, fuzzy_duplicates)
    
    if not merge_map:
        print("\nNo merges to perform!")
        return
    
    print(f"\nTotal topics to merge: {len(merge_map)}")
    
    # Read topics
    topics = []
    with open(input_file, 'r', encoding='utf-8') as infile:
        lines = infile.readlines()
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',', 1)
            if len(parts) == 2:
                topic_id = parts[0].strip()
                topic_name = parts[1].strip()
                # Remove any quotes from the name
                topic_name = topic_name.strip('"').strip("'")
                topics.append({'Id': topic_id, 'Name': topic_name})
    
    # Apply merges - remove merged topics
    final_topics = []
    removed_ids = set()
    
    for topic in topics:
        topic_id = topic['Id']
        
        if topic_id in merge_map:
            # This topic is being merged into another - skip it
            removed_ids.add(topic_id)
            continue
        
        final_topics.append(topic)
    
    # Write final topics
    with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        outfile.write('Id,Name\n')
        for topic in final_topics:
            outfile.write(f"{topic['Id']},{topic['Name']}\n")
    
    # Write complete mapping (includes both split and merge operations)
    with open(mapping_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=['Old_ID', 'New_ID', 'Operation'])
        writer.writeheader()
        
        for old_id, new_id in merge_map.items():
            writer.writerow({
                'Old_ID': old_id,
                'New_ID': new_id,
                'Operation': 'merged'
            })
    
    print(f"\nMerge Results:")
    print(f"  Topics merged: {len(removed_ids)}")
    print(f"  Original topic count: {len(topics)}")
    print(f"  Final topic count: {len(final_topics)}")
    print(f"\nOutput saved to {output_file}")
    print(f"Mapping saved to {mapping_file}")
    print(f"\nNext step: Update TopicInstructorPairs with merged IDs")

if __name__ == "__main__":
    merge_duplicates()
