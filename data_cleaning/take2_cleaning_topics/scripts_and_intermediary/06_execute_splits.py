"""
Script to execute the splits based on multi_topic_analysis.txt
and then check for duplicates.
"""

import csv
import re
from difflib import SequenceMatcher

def parse_analysis_file():
    """Parse multi_topic_analysis.txt to get IDs and their split parts."""
    analysis_file = 'multi_topic_analysis.txt'
    splits = {}
    
    with open(analysis_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_id = None
    current_parts = []
    
    for line in lines:
        # Look for ID lines
        id_match = re.match(r'^ID (\d+):', line)
        if id_match:
            # Save previous topic if exists
            if current_id and current_parts:
                splits[current_id] = current_parts
            
            # Start new topic
            current_id = id_match.group(1)
            current_parts = []
        
        # Look for part lines (numbered like "1. Topic Name")
        part_match = re.match(r'^\s+\d+\.\s+(.+)$', line)
        if part_match and current_id:
            part_name = part_match.group(1).strip()
            current_parts.append(part_name)
    
    # Save last topic
    if current_id and current_parts:
        splits[current_id] = current_parts
    
    return splits

def split_topics():
    """Split topics based on the analysis file."""
    input_file = 'TopicNode_NoQuotes.csv'
    output_file = 'TopicNode_Split.csv'
    mapping_file = 'split_mapping.csv'
    
    # Parse analysis file
    splits = parse_analysis_file()
    print(f"Found {len(splits)} topics to split")
    
    # Read original topics - manually parse to avoid CSV issues
    topics = []
    with open(input_file, 'r', encoding='utf-8') as infile:
        lines = infile.readlines()
        # Skip header
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            # Split on first comma only (ID,Name)
            parts = line.split(',', 1)
            if len(parts) == 2:
                topics.append({'Id': parts[0].strip(), 'Name': parts[1].strip()})
    
    print(f"Read {len(topics)} topics from {input_file}")
    
    # Find max ID
    max_id = max(int(row['Id']) for row in topics)
    
    # Process topics
    new_topics = []
    split_mappings = []
    split_count = 0
    
    for row in topics:
        topic_id = row['Id']
        topic_name = row['Name']
        
        if topic_id in splits:
            # Split this topic
            parts = splits[topic_id]
            split_count += 1
            
            # Keep original ID for first part
            new_topics.append({
                'Id': topic_id,
                'Name': parts[0]
            })
            split_mappings.append({
                'Original_ID': topic_id,
                'New_ID': topic_id,
                'Original_Name': topic_name,
                'New_Name': parts[0]
            })
            
            # Create new IDs for remaining parts
            for part in parts[1:]:
                max_id += 1
                new_topics.append({
                    'Id': str(max_id),
                    'Name': part
                })
                split_mappings.append({
                    'Original_ID': topic_id,
                    'New_ID': str(max_id),
                    'Original_Name': topic_name,
                    'New_Name': part
                })
        else:
            # Keep as is
            new_topics.append(row)
    
    # Write output
    with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=['Id', 'Name'])
        writer.writeheader()
        writer.writerows(new_topics)
    
    # Write mapping
    with open(mapping_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=['Original_ID', 'New_ID', 'Original_Name', 'New_Name'])
        writer.writeheader()
        writer.writerows(split_mappings)
    
    print(f"\nSplit Results:")
    print(f"  Topics split: {split_count}")
    print(f"  New topics created: {len(split_mappings) - split_count}")
    print(f"  Original topic count: {len(topics)}")
    print(f"  New topic count: {len(new_topics)}")
    print(f"\nOutput saved to {output_file}")
    print(f"Mapping saved to {mapping_file}")
    
    return new_topics

def normalize_text(text):
    """Normalize text for duplicate detection."""
    # Convert to lowercase
    text = text.lower()
    # Remove special characters but keep spaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text

def find_duplicates(topics):
    """Find exact and fuzzy duplicates in the split topics."""
    duplicates_file = 'split_duplicates_report.txt'
    
    # Normalize topics
    normalized = {}
    for topic in topics:
        topic_id = topic['Id']
        topic_name = topic['Name']
        norm_name = normalize_text(topic_name)
        
        if norm_name not in normalized:
            normalized[norm_name] = []
        normalized[norm_name].append((topic_id, topic_name))
    
    # Find exact duplicates
    exact_duplicates = {k: v for k, v in normalized.items() if len(v) > 1}
    
    # Find fuzzy duplicates (85% similarity)
    fuzzy_duplicates = []
    topic_list = [(t['Id'], t['Name'], normalize_text(t['Name'])) for t in topics]
    
    for i in range(len(topic_list)):
        for j in range(i + 1, len(topic_list)):
            id1, name1, norm1 = topic_list[i]
            id2, name2, norm2 = topic_list[j]
            
            similarity = SequenceMatcher(None, norm1, norm2).ratio()
            if similarity >= 0.85 and norm1 != norm2:
                fuzzy_duplicates.append((similarity, id1, name1, id2, name2))
    
    # Sort fuzzy duplicates by similarity
    fuzzy_duplicates.sort(reverse=True)
    
    # Write report
    with open(duplicates_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("DUPLICATE DETECTION REPORT (AFTER SPLITTING)\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"EXACT DUPLICATES: {len(exact_duplicates)} groups\n")
        f.write("=" * 80 + "\n")
        for norm_name, topics_list in exact_duplicates.items():
            f.write(f"\nDuplicate Group (normalized: {norm_name}):\n")
            for topic_id, topic_name in topics_list:
                f.write(f"  ID {topic_id}: {topic_name}\n")
        
        f.write("\n\n" + "=" * 80 + "\n")
        f.write(f"FUZZY DUPLICATES (>=85% similar): {len(fuzzy_duplicates)} pairs\n")
        f.write("=" * 80 + "\n\n")
        for similarity, id1, name1, id2, name2 in fuzzy_duplicates:
            f.write(f"Similarity: {similarity:.2%}\n")
            f.write(f"  ID {id1}: {name1}\n")
            f.write(f"  ID {id2}: {name2}\n\n")
    
    print(f"\nDuplicate Detection Results:")
    print(f"  Exact duplicate groups: {len(exact_duplicates)}")
    print(f"  Fuzzy duplicate pairs (>=85%): {len(fuzzy_duplicates)}")
    print(f"\nReport saved to {duplicates_file}")
    
    return exact_duplicates, fuzzy_duplicates

if __name__ == "__main__":
    print("Step 1: Splitting multi-topics...")
    print("=" * 80)
    new_topics = split_topics()
    
    print("\n\nStep 2: Checking for duplicates...")
    print("=" * 80)
    exact_dups, fuzzy_dups = find_duplicates(new_topics)
    
    print("\n" + "=" * 80)
    print("COMPLETE!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review split_duplicates_report.txt")
    print("2. If duplicates found, we can merge them")
    print("3. Update TopicInstructorPairs with new IDs")
