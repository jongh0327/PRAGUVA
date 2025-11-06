"""
Generate CSV files for each hierarchy level with unique IDs.

ID Scheme:
- Level 1 (Major Categories): 1-9
- Level 2 (Subcategories): 101-199
- Level 3 (Sub-subcategories): 1001-1999
- Leaf Topics: 2000+ (existing IDs from TopicNode_Ultima.csv)
"""

import re
import csv

def parse_hierarchy(file_path):
    """Parse Hierarchy.txt and extract all levels."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    level1_nodes = []  # ## 1. MAJOR CATEGORY
    level2_nodes = []  # ### 1.1 Subcategory
    level3_nodes = []  # #### 1.1.1 Sub-subcategory
    
    level1_counter = 1
    level2_counter = 101
    level3_counter = 1001
    
    current_level1_id = None
    current_level1_name = None
    current_level2_id = None
    current_level2_name = None
    
    for line in lines:
        line = line.rstrip()
        
        # Match Level 1: ## 1. MAJOR CATEGORY
        level1_match = re.match(r'^## (\d+)\.\s+(.+)$', line)
        if level1_match:
            num = level1_match.group(1)
            name = level1_match.group(2)
            current_level1_id = level1_counter
            current_level1_name = name
            level1_nodes.append({
                'Id': current_level1_id,
                'Name': name,
                'Number': num
            })
            level1_counter += 1
            current_level2_id = None
            current_level2_name = None
            continue
        
        # Match Level 2: ### 1.1 Subcategory
        level2_match = re.match(r'^### ([\d.]+)\s+(.+)$', line)
        if level2_match:
            num = level2_match.group(1)
            name = level2_match.group(2)
            current_level2_id = level2_counter
            current_level2_name = name
            level2_nodes.append({
                'Id': current_level2_id,
                'Name': name,
                'Number': num,
                'ParentId': current_level1_id,
                'ParentName': current_level1_name
            })
            level2_counter += 1
            continue
        
        # Match Level 3: #### 1.1.1 Sub-subcategory
        level3_match = re.match(r'^#### ([\d.]+)\s+(.+)$', line)
        if level3_match:
            num = level3_match.group(1)
            name = level3_match.group(2)
            level3_id = level3_counter
            level3_nodes.append({
                'Id': level3_id,
                'Name': name,
                'Number': num,
                'ParentId': current_level2_id,
                'ParentName': current_level2_name,
                'GrandParentId': current_level1_id,
                'GrandParentName': current_level1_name
            })
            level3_counter += 1
            continue
    
    return level1_nodes, level2_nodes, level3_nodes


def write_csv(nodes, filename, include_parent=False):
    """Write nodes to CSV file."""
    if not nodes:
        print(f"No nodes to write for {filename}")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        if include_parent:
            fieldnames = ['Id', 'Name', 'ParentId']
        else:
            fieldnames = ['Id', 'Name']
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for node in nodes:
            row = {'Id': node['Id'], 'Name': node['Name']}
            if include_parent and 'ParentId' in node:
                row['ParentId'] = node['ParentId']
            writer.writerow(row)
    
    print(f"✓ Created {filename} with {len(nodes)} nodes")


def main():
    hierarchy_file = 'Hierarchy.txt'
    
    print("Parsing hierarchy...")
    level1, level2, level3 = parse_hierarchy(hierarchy_file)
    
    print(f"\nFound:")
    print(f"  Level 1 (Major Categories): {len(level1)} nodes")
    print(f"  Level 2 (Subcategories): {len(level2)} nodes")
    print(f"  Level 3 (Sub-subcategories): {len(level3)} nodes")
    
    # Write Level 1 nodes (no parent, they are top-level)
    write_csv(level1, 'Level1_Nodes.csv', include_parent=False)
    
    # Write Level 2 nodes (with ParentId)
    write_csv(level2, 'Level2_Nodes.csv', include_parent=True)
    
    # Write Level 3 nodes (with ParentId)
    write_csv(level3, 'Level3_Nodes.csv', include_parent=True)
    
    print("\n" + "="*60)
    print("SUMMARY:")
    print("="*60)
    print(f"Level 1 IDs: {level1[0]['Id']} - {level1[-1]['Id']}")
    print(f"Level 2 IDs: {level2[0]['Id']} - {level2[-1]['Id']}")
    print(f"Level 3 IDs: {level3[0]['Id']} - {level3[-1]['Id']}")
    print("\nLeaf topics (TopicNode_Ultima.csv) should use IDs starting from 2000")
    print("="*60)
    
    # Show some examples
    print("\nSample Level 1 nodes:")
    for node in level1[:3]:
        print(f"  {node['Id']}: {node['Name']}")
    
    print("\nSample Level 2 nodes:")
    for node in level2[:3]:
        print(f"  {node['Id']}: {node['Name']} (Parent: {node['ParentId']})")
    
    print("\nSample Level 3 nodes:")
    for node in level3[:3]:
        print(f"  {node['Id']}: {node['Name']} (Parent: {node['ParentId']})")


if __name__ == '__main__':
    main()
