import csv
from collections import defaultdict

# Read valid TopicIDs from Topic_Hierarchy_Mapping_Final.csv
valid_topic_ids = set()
hierarchy_file = r'c:\Users\jdog1\OneDrive\Documents\Fall 2025\Capstone\PRAGUVA\data_cleaning\Topic_Hierarchy_Mapping_Final.csv'

print("Reading valid TopicIDs from Topic_Hierarchy_Mapping_Final.csv...")
with open(hierarchy_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        valid_topic_ids.add(int(row['TopicID']))

print(f"Found {len(valid_topic_ids)} valid TopicIDs")
print(f"Valid ID range: {min(valid_topic_ids)} to {max(valid_topic_ids)}")

# Read TopicInstructorPairs and track orphaned IDs
pairs_file = r'c:\Users\jdog1\OneDrive\Documents\Fall 2025\Capstone\PRAGUVA\data_cleaning\TopicInstructorPairs_Final.csv'
orphaned_topics = defaultdict(int)  # {topic_id: count of relationships}
valid_pairs = []
total_pairs = 0

print("\nAnalyzing TopicInstructorPairs_Final.csv...")
with open(pairs_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        total_pairs += 1
        topic_id = int(row['TopicID'])
        instructor_id = int(row['InstructorID'])
        
        if topic_id in valid_topic_ids:
            valid_pairs.append((topic_id, instructor_id))
        else:
            orphaned_topics[topic_id] += 1

# Summary statistics
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"Total relationships in TopicInstructorPairs: {total_pairs}")
print(f"Valid relationships (TopicID exists): {len(valid_pairs)}")
print(f"Orphaned relationships (TopicID missing): {sum(orphaned_topics.values())}")
print(f"Number of orphaned TopicIDs: {len(orphaned_topics)}")
print(f"Percentage orphaned: {sum(orphaned_topics.values()) / total_pairs * 100:.1f}%")

# List orphaned TopicIDs
print(f"\n{'='*60}")
print("ORPHANED TOPIC IDs (sorted by ID)")
print(f"{'='*60}")
print(f"{'TopicID':<12} {'# Relationships':<20}")
print(f"{'-'*12} {'-'*20}")

orphaned_sorted = sorted(orphaned_topics.items())
for topic_id, count in orphaned_sorted:
    print(f"{topic_id:<12} {count:<20}")

# Show gaps in valid TopicIDs
print(f"\n{'='*60}")
print("GAPS IN VALID TOPIC IDs")
print(f"{'='*60}")
sorted_valid = sorted(valid_topic_ids)
gaps = []
for i in range(len(sorted_valid) - 1):
    if sorted_valid[i+1] - sorted_valid[i] > 1:
        gap_start = sorted_valid[i] + 1
        gap_end = sorted_valid[i+1] - 1
        gaps.append((gap_start, gap_end))

if gaps:
    print("Missing TopicID ranges:")
    for gap_start, gap_end in gaps:
        if gap_start == gap_end:
            print(f"  - {gap_start}")
        else:
            print(f"  - {gap_start} to {gap_end}")
else:
    print("No gaps found (IDs are consecutive)")

# Write cleaned pairs file
output_file = r'c:\Users\jdog1\OneDrive\Documents\Fall 2025\Capstone\PRAGUVA\data_cleaning\TopicInstructorPairs_Cleaned.csv'
print(f"\n{'='*60}")
print(f"Writing cleaned file: TopicInstructorPairs_Cleaned.csv")
print(f"{'='*60}")

with open(output_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['TopicID', 'InstructorID'])
    for topic_id, instructor_id in valid_pairs:
        writer.writerow([topic_id, instructor_id])

print(f"✅ Wrote {len(valid_pairs)} valid relationships to {output_file}")

# Write report of orphaned topics
report_file = r'c:\Users\jdog1\OneDrive\Documents\Fall 2025\Capstone\PRAGUVA\data_cleaning\orphaned_topics_report.txt'
with open(report_file, 'w', encoding='utf-8') as f:
    f.write("ORPHANED TOPIC IDs REPORT\n")
    f.write("="*60 + "\n\n")
    f.write(f"Total relationships: {total_pairs}\n")
    f.write(f"Valid relationships: {len(valid_pairs)}\n")
    f.write(f"Orphaned relationships: {sum(orphaned_topics.values())}\n")
    f.write(f"Percentage orphaned: {sum(orphaned_topics.values()) / total_pairs * 100:.1f}%\n\n")
    f.write("Orphaned TopicIDs:\n")
    f.write("-" * 40 + "\n")
    for topic_id, count in orphaned_sorted:
        f.write(f"TopicID {topic_id}: {count} relationship(s)\n")

print(f"✅ Wrote detailed report to {report_file}")
