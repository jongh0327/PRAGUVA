"""
Script to identify and split topics that contain multiple comma-separated topics.

This script analyzes topics that have commas and determines if they represent
multiple distinct topics that should be split.
"""

import csv
import re

def has_multiple_topics(topic_name):
    """
    Determine if a topic name contains multiple distinct topics.
    
    Heuristics:
    1. Contains commas
    2. Parts separated by commas look like distinct topic phrases
    3. Avoid splitting legitimate single topics with commas (e.g., "Design, Modeling, and Analysis")
    """
    # If no comma, it's a single topic
    if ',' not in topic_name:
        return False
    
    # Split by comma
    parts = [part.strip() for part in topic_name.split(',')]
    
    # If only 2 parts and second part is short (likely a clarification), keep together
    if len(parts) == 2 and len(parts[1].split()) <= 3:
        return False
    
    # Check if parts look like conjunctions (And, Or, etc.) - keep together
    conjunction_pattern = r'\b(and|or|&)\b'
    if any(re.search(conjunction_pattern, part, re.IGNORECASE) for part in parts):
        # If it's a list with "and"/"or", it's likely one topic
        return False
    
    # If we have 3+ parts that each look substantive (5+ words or contain capital letters suggesting proper phrases)
    if len(parts) >= 2:
        substantive_parts = [p for p in parts if len(p.split()) >= 3 or any(word[0].isupper() for word in p.split() if word)]
        if len(substantive_parts) >= 2:
            return True
    
    return False

def analyze_multi_topics():
    input_file = 'TopicNode_NoQuotes.csv'
    analysis_file = 'multi_topic_analysis2.txt'
    
    multi_topics = []
    
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        
        for row in reader:
            topic_id = row['Id']
            topic_name = row['Name']
            
            if has_multiple_topics(topic_name):
                parts = [part.strip() for part in topic_name.split(',')]
                multi_topics.append({
                    'id': topic_id,
                    'name': topic_name,
                    'parts': parts
                })
    
    # Write analysis report
    with open(analysis_file, 'w', encoding='utf-8') as outfile:
        outfile.write("=" * 80 + "\n")
        outfile.write("MULTI-TOPIC ANALYSIS REPORT\n")
        outfile.write("=" * 80 + "\n\n")
        outfile.write(f"Found {len(multi_topics)} topics that may contain multiple topics:\n\n")
        
        for item in multi_topics:
            outfile.write(f"ID {item['id']}: {item['name']}\n")
            outfile.write(f"  Suggested split into {len(item['parts'])} topics:\n")
            for i, part in enumerate(item['parts'], 1):
                outfile.write(f"    {i}. {part}\n")
            outfile.write("\n")
    
    print(f"Analysis complete!")
    print(f"Found {len(multi_topics)} topics that may contain multiple topics")
    print(f"Review {analysis_file} to see the details")
    print(f"\nNext step: Review the analysis and create a 'split_decisions.txt' file")
    print(f"Format: One ID per line for topics you want to split")
    
    return multi_topics

def split_topics():
    """
    Split topics based on decisions in split_decisions.txt
    """
    input_file = 'TopicNode_NoQuotes.csv'
    output_file = 'TopicNode_Split.csv'
    mapping_file = 'split_mapping.csv'
    decisions_file = 'split_decisions.txt'
    
    # Read split decisions
    try:
        with open(decisions_file, 'r', encoding='utf-8') as f:
            ids_to_split = set(line.strip() for line in f if line.strip() and not line.startswith('#'))
    except FileNotFoundError:
        print(f"Error: {decisions_file} not found!")
        print("Run analyze mode first, review the analysis, then create split_decisions.txt")
        return
    
    # Read original topics
    topics = []
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        topics = list(reader)
    
    # Find max ID
    max_id = max(int(row['Id']) for row in topics)
    
    # Process topics
    new_topics = []
    split_mappings = []
    
    for row in topics:
        topic_id = row['Id']
        topic_name = row['Name']
        
        if topic_id in ids_to_split:
            # Split this topic
            parts = [part.strip() for part in topic_name.split(',')]
            
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
    
    print(f"Split {len(ids_to_split)} topics into {len(split_mappings)} topics")
    print(f"Original topics: {len(topics)}")
    print(f"New topics: {len(new_topics)}")
    print(f"Output saved to {output_file}")
    print(f"Mapping saved to {mapping_file}")
    print(f"\nNext step: Update TopicInstructorPairs_NoQuotes.csv to include new topic IDs")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'split':
        split_topics()
    else:
        analyze_multi_topics()
