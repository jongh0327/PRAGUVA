import csv
import re
from collections import defaultdict
from difflib import SequenceMatcher

# Common synonyms and abbreviations in engineering/CS topics
SYNONYM_GROUPS = {
    'artificial_intelligence': ['ai', 'artificial intelligence', 'artificial intelligence and machine learning'],
    'machine_learning': ['ml', 'machine learning', 'machine learning and ai'],
    'deep_learning': ['dl', 'deep learning'],
    'natural_language_processing': ['nlp', 'natural language processing'],
    'computer_science': ['cs', 'computer science', 'comp sci'],
    'virtual_reality': ['vr', 'virtual reality'],
    'augmented_reality': ['ar', 'augmented reality'],
    'internet_of_things': ['iot', 'internet of things'],
    'human_computer_interaction': ['hci', 'human computer interaction', 'human-computer interaction'],
    'reinforcement_learning': ['rl', 'reinforcement learning'],
    'convolutional_neural_network': ['cnn', 'convolutional neural network'],
    'computer_aided_design': ['cad', 'computer aided design', 'computer-aided design'],
    'finite_element': ['fe', 'finite element'],
    'computational_fluid_dynamics': ['cfd', 'computational fluid dynamics'],
    'stem': ['stem', 'science technology engineering mathematics'],
}

def normalize_text(text):
    """Normalize text for comparison"""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def get_canonical_form(normalized_text):
    """Replace synonyms with canonical form using whole-word matching"""
    for canonical, synonyms in SYNONYM_GROUPS.items():
        for synonym in sorted(synonyms, key=len, reverse=True):
            if ' ' in synonym:
                pattern = r'\b' + re.escape(synonym) + r'\b'
            else:
                pattern = r'\b' + re.escape(synonym) + r'\b'
            normalized_text = re.sub(pattern, canonical, normalized_text)
    return normalize_text(normalized_text)

def capitalize_words(text):
    """Capitalize each word in the text"""
    # Split by spaces and capitalize each word
    words = text.split()
    capitalized = ' '.join(word.capitalize() for word in words)
    return capitalized

def similarity_ratio(str1, str2):
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, str1, str2).ratio()

def load_topics(filepath):
    """Load topics from TopicNode.csv"""
    topics = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            topics.append({
                'id': int(row['Id']),
                'name': row['Name'],
                'normalized': normalize_text(row['Name']),
                'canonical': get_canonical_form(normalize_text(row['Name']))
            })
    return topics

def parse_keep_separate(filepath):
    """Parse keep_separate.txt to extract ID pairs that should not be merged"""
    protected_pairs = set()
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for similarity percentage lines
        if line.startswith('Similarity:'):
            # Next two lines should contain IDs (skip empty lines)
            ids_found = []
            j = i + 1
            
            # Look for the next two ID lines
            while j < len(lines) and len(ids_found) < 2:
                line_to_check = lines[j].strip()
                
                # Skip empty lines
                if not line_to_check:
                    j += 1
                    continue
                
                # Try to extract ID from line (with flexible spacing)
                match = re.search(r'ID\s+(\d+):', line_to_check)
                if match:
                    ids_found.append(int(match.group(1)))
                    j += 1
                else:
                    # If we hit a non-ID line, break
                    break
            
            # If we found exactly 2 IDs, add as protected pair
            if len(ids_found) == 2:
                id1, id2 = ids_found
                protected_pairs.add((min(id1, id2), max(id1, id2)))
                print(f"  Protected pair: {min(id1, id2)} <-> {max(id1, id2)}")
        
        i += 1
    
    return protected_pairs

def find_exact_duplicates(topics):
    """Find topics with identical canonical forms"""
    canonical_map = defaultdict(list)
    for topic in topics:
        canonical_map[topic['canonical']].append(topic)
    
    duplicates = {k: v for k, v in canonical_map.items() if len(v) > 1}
    return duplicates

def find_fuzzy_duplicates(topics, threshold=0.85):
    """Find topics with high similarity scores"""
    fuzzy_duplicates = []
    
    for i in range(len(topics)):
        for j in range(i + 1, len(topics)):
            topic1 = topics[i]
            topic2 = topics[j]
            
            if topic1['canonical'] == topic2['canonical']:
                continue
            
            sim = similarity_ratio(topic1['canonical'], topic2['canonical'])
            
            if sim >= threshold:
                fuzzy_duplicates.append({
                    'topic1': topic1,
                    'topic2': topic2,
                    'similarity': sim
                })
    
    return fuzzy_duplicates

def should_merge(id1, id2, protected_pairs):
    """Check if two IDs should be merged (not in protected pairs)"""
    pair = (min(id1, id2), max(id1, id2))
    return pair not in protected_pairs

# Load data
input_dir = r'c:\Users\jdog1\OneDrive\Documents\Fall 2025\Capstone\PRAGUVA\data_cleaning\take2_cleaning_topics'
topics_file = f'{input_dir}\\TopicNode.csv'
keep_separate_file = f'{input_dir}\\keep_separate.txt'

print("Loading topics...")
topics = load_topics(topics_file)
print(f"Loaded {len(topics)} topics")

print("\nParsing keep_separate.txt...")
protected_pairs = parse_keep_separate(keep_separate_file)
print(f"Found {len(protected_pairs)} protected ID pairs that will NOT be merged")

# Find duplicates
print("\nFinding exact duplicates...")
exact_dupes = find_exact_duplicates(topics)

print("\nFinding fuzzy duplicates (>85% similarity)...")
fuzzy_dupes = find_fuzzy_duplicates(topics, threshold=0.85)

# Build merge map: old_id -> new_id (primary_id)
merge_map = {}  # old_id -> primary_id
primary_topics = {}  # primary_id -> topic info

print("\n" + "="*80)
print("BUILDING MERGE MAP")
print("="*80)

# Process exact duplicates
print("\nProcessing exact duplicates...")
exact_merge_count = 0
for canonical, dupes in exact_dupes.items():
    # Sort by ID to get primary (lowest ID)
    sorted_dupes = sorted(dupes, key=lambda x: x['id'])
    primary = sorted_dupes[0]
    
    # Check if any pairs are protected
    merge_group = [primary]
    for dupe in sorted_dupes[1:]:
        if should_merge(primary['id'], dupe['id'], protected_pairs):
            merge_map[dupe['id']] = primary['id']
            exact_merge_count += 1
            print(f"  Merging ID {dupe['id']} -> {primary['id']}")
        else:
            print(f"  PROTECTED: Keeping ID {dupe['id']} separate from {primary['id']}")
            merge_group.append(dupe)
    
    # Store primary topic with capitalized name
    if primary['id'] not in primary_topics:
        primary_topics[primary['id']] = {
            'id': primary['id'],
            'name': capitalize_words(primary['name']),
            'original_name': primary['name']
        }

print(f"\nExact duplicates: {exact_merge_count} topics will be merged")

# Process fuzzy duplicates
print("\nProcessing fuzzy duplicates...")
fuzzy_merge_count = 0
for dupe_pair in fuzzy_dupes:
    id1 = dupe_pair['topic1']['id']
    id2 = dupe_pair['topic2']['id']
    
    # Determine primary (lower ID)
    primary_id = min(id1, id2)
    secondary_id = max(id1, id2)
    
    # Skip if secondary is already merged to something else
    if secondary_id in merge_map:
        continue
    
    # Skip if either is already a primary topic from exact duplicates
    # (unless we're merging TO that primary)
    if secondary_id in primary_topics:
        continue
    
    # Check if protected
    if should_merge(id1, id2, protected_pairs):
        merge_map[secondary_id] = primary_id
        fuzzy_merge_count += 1
        print(f"  Merging ID {secondary_id} -> {primary_id} (similarity: {dupe_pair['similarity']:.2%})")
        
        # Ensure primary is in primary_topics
        if primary_id not in primary_topics:
            primary_topic = dupe_pair['topic1'] if id1 == primary_id else dupe_pair['topic2']
            primary_topics[primary_id] = {
                'id': primary_id,
                'name': capitalize_words(primary_topic['name']),
                'original_name': primary_topic['name']
            }
    else:
        print(f"  PROTECTED: Keeping ID {secondary_id} separate from {primary_id}")

print(f"\nFuzzy duplicates: {fuzzy_merge_count} topics will be merged")

# Add non-duplicate topics to primary_topics
print("\nAdding non-duplicate topics...")
for topic in topics:
    if topic['id'] not in merge_map and topic['id'] not in primary_topics:
        primary_topics[topic['id']] = {
            'id': topic['id'],
            'name': capitalize_words(topic['name']),
            'original_name': topic['name']
        }

print(f"\nTotal topics after deduplication: {len(primary_topics)}")
print(f"Total topics merged: {len(merge_map)}")

# Write deduplicated TopicNode.csv
output_topics_file = f'{input_dir}\\TopicNode_Deduplicated.csv'
print(f"\n" + "="*80)
print(f"Writing deduplicated topics to: TopicNode_Deduplicated.csv")
print("="*80)

with open(output_topics_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Id', 'Name'])
    
    for topic_id in sorted(primary_topics.keys()):
        topic = primary_topics[topic_id]
        writer.writerow([topic['id'], topic['name']])

print(f"✅ Wrote {len(primary_topics)} deduplicated topics")

# Write ID mapping file
mapping_file = f'{input_dir}\\id_mapping.csv'
print(f"\nWriting ID mapping to: id_mapping.csv")

with open(mapping_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['OldTopicID', 'NewTopicID', 'Action'])
    
    # Write merged topics
    for old_id in sorted(merge_map.keys()):
        new_id = merge_map[old_id]
        writer.writerow([old_id, new_id, 'Merged'])
    
    # Write kept topics
    for topic_id in sorted(primary_topics.keys()):
        writer.writerow([topic_id, topic_id, 'Kept'])

print(f"✅ Wrote ID mapping for {len(merge_map) + len(primary_topics)} topics")

# Update TopicInstructorPairs
pairs_file = f'{input_dir}\\TopicInstructorPairs.csv'
output_pairs_file = f'{input_dir}\\TopicInstructorPairs_Deduplicated.csv'

print(f"\n" + "="*80)
print(f"Updating TopicInstructorPairs...")
print("="*80)

pairs = []
with open(pairs_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        old_topic_id = int(row['TopicID'])
        instructor_id = int(row['InstructorID'])
        
        # Map to new ID if merged
        new_topic_id = merge_map.get(old_topic_id, old_topic_id)
        pairs.append((new_topic_id, instructor_id))

# Remove duplicates (same topic-instructor pair may appear after merging)
unique_pairs = sorted(set(pairs))

with open(output_pairs_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['TopicID', 'InstructorID'])
    for topic_id, instructor_id in unique_pairs:
        writer.writerow([topic_id, instructor_id])

print(f"Original pairs: {len(pairs)}")
print(f"After deduplication: {len(unique_pairs)}")
print(f"Duplicate pairs removed: {len(pairs) - len(unique_pairs)}")
print(f"✅ Wrote updated TopicInstructorPairs_Deduplicated.csv")

# Generate summary report
summary_file = f'{input_dir}\\deduplication_summary.txt'
print(f"\n" + "="*80)
print(f"Writing summary report...")
print("="*80)

with open(summary_file, 'w', encoding='utf-8') as f:
    f.write("TOPIC DEDUPLICATION SUMMARY\n")
    f.write("="*80 + "\n\n")
    
    f.write("STATISTICS\n")
    f.write("-"*80 + "\n")
    f.write(f"Original topics: {len(topics)}\n")
    f.write(f"Deduplicated topics: {len(primary_topics)}\n")
    f.write(f"Topics merged: {len(merge_map)}\n")
    f.write(f"Protected pairs (kept separate): {len(protected_pairs)}\n")
    f.write(f"Exact duplicate merges: {exact_merge_count}\n")
    f.write(f"Fuzzy duplicate merges: {fuzzy_merge_count}\n\n")
    
    f.write("MERGED TOPICS\n")
    f.write("-"*80 + "\n")
    for old_id in sorted(merge_map.keys()):
        new_id = merge_map[old_id]
        old_topic = next(t for t in topics if t['id'] == old_id)
        new_topic = primary_topics[new_id]
        f.write(f"ID {old_id}: {old_topic['name']}\n")
        f.write(f"  -> Merged into ID {new_id}: {new_topic['name']}\n\n")

print(f"✅ Wrote summary report to: deduplication_summary.txt")

print("\n" + "="*80)
print("DEDUPLICATION COMPLETE!")
print("="*80)
print("\nGenerated files:")
print(f"  1. TopicNode_Deduplicated.csv - {len(primary_topics)} deduplicated topics")
print(f"  2. id_mapping.csv - Mapping of old IDs to new IDs")
print(f"  3. TopicInstructorPairs_Deduplicated.csv - Updated instructor relationships")
print(f"  4. deduplication_summary.txt - Detailed summary report")
print("\nNext steps:")
print("  1. Review the summary report")
print("  2. Verify the deduplicated topics")
print("  3. Proceed with hierarchical classification")
