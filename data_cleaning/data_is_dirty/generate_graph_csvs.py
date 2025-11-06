import csv
from collections import defaultdict

def parse_hierarchy_code(category_str):
    """Extract the numeric code from category string like '1.3 Tissue Engineering'"""
    if not category_str:
        return None
    parts = category_str.split(' ', 1)
    return parts[0] if parts else None

def generate_level1_id(code):
    """Convert '1' to 1, '2' to 2, etc."""
    return int(code.split('.')[0])

def generate_level2_id(code):
    """Convert '1.3' to 103, '2.1' to 201, etc."""
    parts = code.split('.')
    if len(parts) >= 2:
        return int(parts[0]) * 100 + int(parts[1])
    return None

def generate_level3_id(code):
    """Convert '1.3.4' to 10304, '2.1.3' to 20103, etc."""
    parts = code.split('.')
    if len(parts) >= 3:
        return int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2])
    return None

def extract_category_name(category_str):
    """Extract name from '1.3 Tissue Engineering' -> 'Tissue Engineering'"""
    if not category_str:
        return None
    parts = category_str.split(' ', 1)
    return parts[1] if len(parts) > 1 else parts[0]

# Read the source CSV
input_file = r'c:\Users\jdog1\OneDrive\Documents\Fall 2025\Capstone\PRAGUVA\data_cleaning\Topic_Hierarchy_Mapping_Final.csv'

# Data structures to store unique nodes
level1_nodes = {}  # {id: name}
level2_nodes = {}  # {id: (name, parent_id)}
level3_nodes = {}  # {id: (name, parent_id)}
topics = []  # [(topic_id, topic_name, parent_id)]

print("Reading source CSV...")
with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    
    for row in reader:
        topic_id = row['TopicID']
        topic_name = row['TopicName']
        level1_str = row['Level1_Category']
        level2_str = row['Level2_Category']
        level3_str = row['Level3_Category']
        
        # Process Level 1
        if level1_str:
            code1 = parse_hierarchy_code(level1_str)
            id1 = generate_level1_id(code1)
            name1 = extract_category_name(level1_str)
            if id1 not in level1_nodes:
                level1_nodes[id1] = name1
        
        # Process Level 2
        if level2_str:
            code2 = parse_hierarchy_code(level2_str)
            id2 = generate_level2_id(code2)
            name2 = extract_category_name(level2_str)
            parent2 = generate_level1_id(code2)
            if id2 not in level2_nodes:
                level2_nodes[id2] = (name2, parent2)
        
        # Process Level 3
        parent_id = None
        if level3_str:
            code3 = parse_hierarchy_code(level3_str)
            id3 = generate_level3_id(code3)
            name3 = extract_category_name(level3_str)
            parent3 = generate_level2_id(code3)
            if id3 not in level3_nodes:
                level3_nodes[id3] = (name3, parent3)
            parent_id = id3
        elif level2_str:
            # Topic only goes to Level 2
            code2 = parse_hierarchy_code(level2_str)
            parent_id = generate_level2_id(code2)
        
        # Add topic
        topics.append((topic_id, topic_name, parent_id))

print(f"Found {len(level1_nodes)} Level 1 categories")
print(f"Found {len(level2_nodes)} Level 2 categories")
print(f"Found {len(level3_nodes)} Level 3 categories")
print(f"Found {len(topics)} topics")

# Write Level 1 CSV
output_dir = r'c:\Users\jdog1\OneDrive\Documents\Fall 2025\Capstone\PRAGUVA\data_cleaning'
level1_file = f'{output_dir}\\level1_nodes.csv'
print(f"\nWriting {level1_file}...")
with open(level1_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['NodeID', 'NodeName', 'ParentID'])
    for node_id in sorted(level1_nodes.keys()):
        writer.writerow([node_id, level1_nodes[node_id], ''])

# Write Level 2 CSV
level2_file = f'{output_dir}\\level2_nodes.csv'
print(f"Writing {level2_file}...")
with open(level2_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['NodeID', 'NodeName', 'ParentID'])
    for node_id in sorted(level2_nodes.keys()):
        name, parent = level2_nodes[node_id]
        writer.writerow([node_id, name, parent])

# Write Level 3 CSV
level3_file = f'{output_dir}\\level3_nodes.csv'
print(f"Writing {level3_file}...")
with open(level3_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['NodeID', 'NodeName', 'ParentID'])
    for node_id in sorted(level3_nodes.keys()):
        name, parent = level3_nodes[node_id]
        writer.writerow([node_id, name, parent])

# Write Topics CSV
topics_file = f'{output_dir}\\topic_nodes.csv'
print(f"Writing {topics_file}...")
with open(topics_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['TopicID', 'TopicName', 'ParentID'])
    for topic_id, topic_name, parent_id in topics:
        writer.writerow([topic_id, topic_name, parent_id if parent_id else ''])

print("\n✅ All CSV files generated successfully!")
print("\nGenerated files:")
print(f"  - {level1_file}")
print(f"  - {level2_file}")
print(f"  - {level3_file}")
print(f"  - {topics_file}")
