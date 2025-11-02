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
    # Convert to lowercase
    text = text.lower()
    # Remove special characters but keep spaces and alphanumeric
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing spaces
    text = text.strip()
    return text

def get_canonical_form(normalized_text):
    """Replace synonyms with canonical form using whole-word matching"""
    # Use word boundaries to avoid partial matches
    # Sort synonyms by length (longest first) to handle multi-word phrases
    for canonical, synonyms in SYNONYM_GROUPS.items():
        for synonym in sorted(synonyms, key=len, reverse=True):
            # Create regex pattern with word boundaries
            # Use \b for single words, or match exact phrase for multi-word
            if ' ' in synonym:
                # Multi-word phrase - match exact phrase with word boundaries
                pattern = r'\b' + re.escape(synonym) + r'\b'
            else:
                # Single word - use word boundaries
                pattern = r'\b' + re.escape(synonym) + r'\b'
            
            normalized_text = re.sub(pattern, canonical, normalized_text)
    
    return normalize_text(normalized_text)  # Re-normalize after replacements

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
            
            # Skip if already exact duplicates
            if topic1['canonical'] == topic2['canonical']:
                continue
            
            # Calculate similarity
            sim = similarity_ratio(topic1['canonical'], topic2['canonical'])
            
            if sim >= threshold:
                fuzzy_duplicates.append({
                    'topic1': topic1,
                    'topic2': topic2,
                    'similarity': sim
                })
    
    return sorted(fuzzy_duplicates, key=lambda x: x['similarity'], reverse=True)

def find_substring_matches(topics):
    """Find topics where one is a substring of another"""
    substring_matches = []
    
    for i in range(len(topics)):
        for j in range(i + 1, len(topics)):
            topic1 = topics[i]
            topic2 = topics[j]
            
            canonical1 = topic1['canonical']
            canonical2 = topic2['canonical']
            
            # Check if one is substring of the other
            if canonical1 in canonical2 or canonical2 in canonical1:
                substring_matches.append({
                    'shorter': topic1 if len(canonical1) < len(canonical2) else topic2,
                    'longer': topic2 if len(canonical1) < len(canonical2) else topic1
                })
    
    return substring_matches

# Load topics
input_file = r'c:\Users\jdog1\OneDrive\Documents\Fall 2025\Capstone\PRAGUVA\data_cleaning\take2_cleaning_topics\TopicNode.csv'
print("Loading topics from TopicNode.csv...")
topics = load_topics(input_file)
print(f"Loaded {len(topics)} topics")

# Find exact duplicates
print("\n" + "="*80)
print("FINDING EXACT DUPLICATES")
print("="*80)
exact_dupes = find_exact_duplicates(topics)
print(f"\nFound {len(exact_dupes)} groups of exact duplicates:")

exact_dupe_count = 0
for canonical, dupes in sorted(exact_dupes.items(), key=lambda x: len(x[1]), reverse=True):
    exact_dupe_count += len(dupes)
    print(f"\n  Canonical form: '{canonical}'")
    print(f"  {len(dupes)} instances:")
    for topic in dupes:
        print(f"    - ID {topic['id']:4d}: {topic['name']}")

# Find fuzzy duplicates
print("\n" + "="*80)
print("FINDING FUZZY DUPLICATES (>85% similar)")
print("="*80)
fuzzy_dupes = find_fuzzy_duplicates(topics, threshold=0.85)
print(f"\nFound {len(fuzzy_dupes)} potential fuzzy duplicate pairs:")

for dupe in fuzzy_dupes[:50]:  # Show top 50
    print(f"\n  Similarity: {dupe['similarity']:.2%}")
    print(f"    ID {dupe['topic1']['id']:4d}: {dupe['topic1']['name']}")
    print(f"    ID {dupe['topic2']['id']:4d}: {dupe['topic2']['name']}")

if len(fuzzy_dupes) > 50:
    print(f"\n  ... and {len(fuzzy_dupes) - 50} more (see full report file)")

# Find substring matches
print("\n" + "="*80)
print("FINDING SUBSTRING MATCHES")
print("="*80)
substring_matches = find_substring_matches(topics)
print(f"\nFound {len(substring_matches)} substring matches:")

for match in substring_matches[:30]:  # Show top 30
    print(f"\n  Shorter: ID {match['shorter']['id']:4d}: {match['shorter']['name']}")
    print(f"  Longer:  ID {match['longer']['id']:4d}: {match['longer']['name']}")

if len(substring_matches) > 30:
    print(f"\n  ... and {len(substring_matches) - 30} more (see full report file)")

# Generate detailed report
output_dir = r'c:\Users\jdog1\OneDrive\Documents\Fall 2025\Capstone\PRAGUVA\data_cleaning\take2_cleaning_topics'
report_file = f'{output_dir}\\duplicate_analysis_report.txt'

print(f"\n" + "="*80)
print("WRITING DETAILED REPORT")
print("="*80)

with open(report_file, 'w', encoding='utf-8') as f:
    f.write("TOPIC DUPLICATE ANALYSIS REPORT\n")
    f.write("="*80 + "\n\n")
    
    # Summary
    f.write("SUMMARY\n")
    f.write("-"*80 + "\n")
    f.write(f"Total topics analyzed: {len(topics)}\n")
    f.write(f"Exact duplicate groups: {len(exact_dupes)}\n")
    f.write(f"Total exact duplicate instances: {exact_dupe_count}\n")
    f.write(f"Fuzzy duplicate pairs (>85% similar): {len(fuzzy_dupes)}\n")
    f.write(f"Substring matches: {len(substring_matches)}\n\n")
    
    # Exact duplicates
    f.write("\n" + "="*80 + "\n")
    f.write("EXACT DUPLICATES\n")
    f.write("="*80 + "\n\n")
    
    for canonical, dupes in sorted(exact_dupes.items(), key=lambda x: len(x[1]), reverse=True):
        f.write(f"Canonical form: '{canonical}'\n")
        f.write(f"{len(dupes)} instances:\n")
        for topic in dupes:
            f.write(f"  ID {topic['id']:4d}: {topic['name']}\n")
        f.write("\n")
    
    # Fuzzy duplicates
    f.write("\n" + "="*80 + "\n")
    f.write("FUZZY DUPLICATES (>85% similar)\n")
    f.write("="*80 + "\n\n")
    
    for dupe in fuzzy_dupes:
        f.write(f"Similarity: {dupe['similarity']:.2%}\n")
        f.write(f"  ID {dupe['topic1']['id']:4d}: {dupe['topic1']['name']}\n")
        f.write(f"  ID {dupe['topic2']['id']:4d}: {dupe['topic2']['name']}\n")
        f.write("\n")
    
    # Substring matches
    f.write("\n" + "="*80 + "\n")
    f.write("SUBSTRING MATCHES\n")
    f.write("="*80 + "\n\n")
    
    for match in substring_matches:
        f.write(f"Shorter: ID {match['shorter']['id']:4d}: {match['shorter']['name']}\n")
        f.write(f"Longer:  ID {match['longer']['id']:4d}: {match['longer']['name']}\n")
        f.write("\n")

print(f"✅ Detailed report written to: {report_file}")

# Generate synonym mapping report
synonym_report = f'{output_dir}\\synonym_mappings.txt'
with open(synonym_report, 'w', encoding='utf-8') as f:
    f.write("SYNONYM GROUPS USED FOR NORMALIZATION\n")
    f.write("="*80 + "\n\n")
    
    for canonical, synonyms in sorted(SYNONYM_GROUPS.items()):
        f.write(f"{canonical}:\n")
        for syn in synonyms:
            f.write(f"  - {syn}\n")
        f.write("\n")

print(f"✅ Synonym mappings written to: {synonym_report}")

print("\n" + "="*80)
print("NEXT STEPS")
print("="*80)
print("1. Review the detailed report file")
print("2. Decide which duplicates to merge")
print("3. Run the deduplication script (next step)")
print("4. Assign topics to hierarchy categories")
print("5. Generate new IDs and update instructor relationships")
