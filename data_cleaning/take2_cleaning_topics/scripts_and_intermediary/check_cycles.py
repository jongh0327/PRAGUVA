#!/usr/bin/env python3
"""
Diagnostic script to check for circular references in TopicParentPairs.csv
"""

import csv

PARENT_PAIRS_FILE = 'TopicParentPairs.csv'

def check_for_cycles():
    # Build parent lookup
    parent_lookup = {}
    
    with open(PARENT_PAIRS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            child_id = row['ChildTopicID']
            parent_id = row['ParentTopicID']
            parent_lookup[child_id] = parent_id
    
    print(f"Total parent-child relationships: {len(parent_lookup)}")
    
    # Check each topic for cycles
    cycles_found = []
    max_depth = 0
    
    for start_id in parent_lookup.keys():
        current_id = start_id
        visited = set()
        depth = 0
        
        while current_id in parent_lookup:
            if current_id in visited:
                cycle_path = [start_id]
                temp_id = start_id
                while temp_id != current_id:
                    temp_id = parent_lookup[temp_id]
                    cycle_path.append(temp_id)
                cycle_path.append(current_id)
                cycles_found.append(cycle_path)
                break
            
            visited.add(current_id)
            current_id = parent_lookup[current_id]
            depth += 1
            
            if depth > 100:  # Safety check
                print(f"⚠️  Very deep hierarchy detected for topic {start_id} (depth > 100)")
                break
        
        max_depth = max(max_depth, depth)
    
    print(f"\nMax hierarchy depth: {max_depth}")
    
    if cycles_found:
        print(f"\n❌ Found {len(cycles_found)} circular references:")
        for i, cycle in enumerate(cycles_found[:10], 1):  # Show first 10
            print(f"  {i}. {' → '.join(cycle)}")
    else:
        print("\n✅ No circular references found!")

if __name__ == "__main__":
    check_for_cycles()
