import csv
import re
from collections import defaultdict

def parse_hierarchy(filepath):
    """Parse Hierarchy.txt to extract the category structure and example topics"""
    hierarchy = {}
    current_level1 = None
    current_level2 = None
    current_level3 = None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.rstrip()
        
        # Level 1: ## 1. CATEGORY
        match1 = re.match(r'^##\s+(\d+)\.\s+(.+)$', line)
        if match1:
            level1_num = match1.group(1)
            level1_name = match1.group(2).strip()
            current_level1 = f"{level1_num}. {level1_name}"
            hierarchy[current_level1] = {'level2': {}, 'examples': []}
            current_level2 = None
            current_level3 = None
            continue
        
        # Level 2: ### 1.1 Subcategory
        match2 = re.match(r'^###\s+([\d\.]+)\s+(.+)$', line)
        if match2 and current_level1:
            level2_code = match2.group(1)
            level2_name = match2.group(2).strip()
            current_level2 = f"{level2_code} {level2_name}"
            hierarchy[current_level1]['level2'][current_level2] = {'level3': {}, 'examples': []}
            current_level3 = None
            continue
        
        # Level 3: #### 1.1.1 Sub-subcategory
        match3 = re.match(r'^####\s+([\d\.]+)\s+(.+)$', line)
        if match3 and current_level1 and current_level2:
            level3_code = match3.group(1)
            level3_name = match3.group(2).strip()
            current_level3 = f"{level3_code} {level3_name}"
            hierarchy[current_level1]['level2'][current_level2]['level3'][current_level3] = {'examples': []}
            continue
        
        # Example topic: - Topic Name
        match_example = re.match(r'^-\s+(.+)$', line)
        if match_example:
            example = match_example.group(1).strip()
            
            # Add to current level3 if exists, else level2, else level1
            if current_level3:
                hierarchy[current_level1]['level2'][current_level2]['level3'][current_level3]['examples'].append(example)
            elif current_level2:
                hierarchy[current_level1]['level2'][current_level2]['examples'].append(example)
            elif current_level1:
                hierarchy[current_level1]['examples'].append(example)
    
    return hierarchy

def normalize_for_matching(text):
    """Normalize text for keyword matching"""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def find_best_match(topic_name, hierarchy):
    """Find the best hierarchical match for a topic using keyword matching"""
    topic_normalized = normalize_for_matching(topic_name)
    topic_words = set(topic_normalized.split())
    
    best_match = None
    best_score = 0
    
    for level1, level1_data in hierarchy.items():
        # Check Level 1 examples
        for example in level1_data['examples']:
            example_words = set(normalize_for_matching(example).split())
            overlap = len(topic_words & example_words)
            if overlap > best_score:
                best_score = overlap
                best_match = (level1, None, None, example)
        
        # Check Level 2
        for level2, level2_data in level1_data['level2'].items():
            # Check Level 2 examples
            for example in level2_data['examples']:
                example_words = set(normalize_for_matching(example).split())
                overlap = len(topic_words & example_words)
                if overlap > best_score:
                    best_score = overlap
                    best_match = (level1, level2, None, example)
            
            # Check Level 3
            for level3, level3_data in level2_data['level3'].items():
                # Check Level 3 examples
                for example in level3_data['examples']:
                    example_words = set(normalize_for_matching(example).split())
                    overlap = len(topic_words & example_words)
                    if overlap > best_score:
                        best_score = overlap
                        best_match = (level1, level2, level3, example)
    
    # If no good match found (score < 2), leave unclassified
    if best_score < 2:
        return (None, None, None, None, 0)
    
    return (*best_match, best_score)

def load_deduplicated_topics(filepath):
    """Load deduplicated topics"""
    topics = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            topics.append({
                'id': int(row['Id']),
                'name': row['Name']
            })
    return topics

# Main execution
input_dir = r'c:\Users\jdog1\OneDrive\Documents\Fall 2025\Capstone\PRAGUVA\data_cleaning\take2_cleaning_topics'
hierarchy_file = f'{input_dir}\\Hierarchy.txt'
topics_file = f'{input_dir}\\TopicNode_Deduplicated.csv'

print("Parsing hierarchy structure...")
hierarchy = parse_hierarchy(hierarchy_file)

# Count categories
level1_count = len(hierarchy)
level2_count = sum(len(l1['level2']) for l1 in hierarchy.values())
level3_count = sum(
    len(l2['level3']) 
    for l1 in hierarchy.values() 
    for l2 in l1['level2'].values()
)

print(f"Found:")
print(f"  {level1_count} Level 1 categories")
print(f"  {level2_count} Level 2 categories")
print(f"  {level3_count} Level 3 categories")

print("\nLoading deduplicated topics...")
topics = load_deduplicated_topics(topics_file)
print(f"Loaded {len(topics)} topics")

print("\n" + "="*80)
print("CLASSIFYING TOPICS")
print("="*80)

classifications = []
unclassified = []

for i, topic in enumerate(topics, 1):
    level1, level2, level3, matched_example, score = find_best_match(topic['name'], hierarchy)
    
    if level1 is None:
        unclassified.append(topic)
        classifications.append({
            'id': topic['id'],
            'name': topic['name'],
            'level1': '',
            'level2': '',
            'level3': '',
            'matched_example': '',
            'confidence_score': 0
        })
        print(f"  [{i}/{len(topics)}] UNCLASSIFIED: {topic['name']}")
    else:
        classifications.append({
            'id': topic['id'],
            'name': topic['name'],
            'level1': level1 or '',
            'level2': level2 or '',
            'level3': level3 or '',
            'matched_example': matched_example or '',
            'confidence_score': score
        })
        if i % 50 == 0:
            print(f"  [{i}/{len(topics)}] Classified...")

print(f"\nClassification complete!")
print(f"  Classified: {len(topics) - len(unclassified)}")
print(f"  Unclassified: {len(unclassified)}")

# Write initial classification
output_file = f'{input_dir}\\TopicNode_Classified_Draft.csv'
print(f"\n" + "="*80)
print(f"Writing draft classification to: TopicNode_Classified_Draft.csv")
print("="*80)

with open(output_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['TopicID', 'TopicName', 'Level1_Category', 'Level2_Category', 'Level3_Category', 'Matched_Example', 'Confidence_Score'])
    
    for c in classifications:
        writer.writerow([
            c['id'],
            c['name'],
            c['level1'],
            c['level2'],
            c['level3'],
            c['matched_example'],
            c['confidence_score']
        ])

print(f"✅ Wrote draft classification")

# Write unclassified topics for manual review
if unclassified:
    unclassified_file = f'{input_dir}\\Unclassified_Topics.txt'
    print(f"\nWriting unclassified topics to: Unclassified_Topics.txt")
    
    with open(unclassified_file, 'w', encoding='utf-8') as f:
        f.write("UNCLASSIFIED TOPICS REQUIRING MANUAL CLASSIFICATION\n")
        f.write("="*80 + "\n\n")
        f.write(f"Total unclassified: {len(unclassified)}\n\n")
        
        for topic in unclassified:
            f.write(f"ID {topic['id']:4d}: {topic['name']}\n")
    
    print(f"✅ Wrote {len(unclassified)} unclassified topics")

# Generate classification summary
summary_file = f'{input_dir}\\classification_summary.txt'
print(f"\nWriting classification summary...")

# Count topics by Level 1 category
level1_counts = defaultdict(int)
for c in classifications:
    if c['level1']:
        level1_counts[c['level1']] += 1

with open(summary_file, 'w', encoding='utf-8') as f:
    f.write("TOPIC CLASSIFICATION SUMMARY\n")
    f.write("="*80 + "\n\n")
    
    f.write("STATISTICS\n")
    f.write("-"*80 + "\n")
    f.write(f"Total topics: {len(topics)}\n")
    f.write(f"Classified: {len(topics) - len(unclassified)}\n")
    f.write(f"Unclassified: {len(unclassified)}\n")
    f.write(f"Classification rate: {(len(topics) - len(unclassified)) / len(topics) * 100:.1f}%\n\n")
    
    f.write("DISTRIBUTION BY LEVEL 1 CATEGORY\n")
    f.write("-"*80 + "\n")
    for level1 in sorted(level1_counts.keys()):
        count = level1_counts[level1]
        percentage = count / len(topics) * 100
        f.write(f"{level1}: {count} topics ({percentage:.1f}%)\n")
    
    if unclassified:
        f.write("\n\nUNCLASSIFIED TOPICS\n")
        f.write("-"*80 + "\n")
        for topic in unclassified:
            f.write(f"ID {topic['id']:4d}: {topic['name']}\n")

print(f"✅ Wrote classification summary")

print("\n" + "="*80)
print("CLASSIFICATION COMPLETE!")
print("="*80)
print("\nGenerated files:")
print(f"  1. TopicNode_Classified_Draft.csv - Draft classification for review")
print(f"  2. Unclassified_Topics.txt - Topics requiring manual classification")
print(f"  3. classification_summary.txt - Summary statistics")
print("\nNext steps:")
print("  1. Review TopicNode_Classified_Draft.csv")
print("  2. Manually classify unclassified topics")
print("  3. Correct any misclassifications")
print("  4. Generate final hierarchical node CSVs")
