#!/usr/bin/env python3
"""
Script to fix TopicNode_Ultima.csv by properly handling commas in category names.
The issue: Category names like "9.4 Science, Technology & Society" are being split
at the comma because they're not quoted.
"""

import csv

INPUT_FILE = 'TopicNode_Ultima.csv'
OUTPUT_FILE = 'TopicNode_Ultima_Fixed.csv'

def fix_csv():
    """
    Read the malformed CSV and fix it by properly quoting fields with commas.
    """
    fixed_rows = []
    issues_found = 0
    
    print("Reading and fixing TopicNode_Ultima.csv...")
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        # Read as raw lines first to handle malformed CSV
        lines = f.readlines()
    
    # Process header
    header = lines[0].strip()
    fixed_rows.append(['TopicID', 'TopicName', 'Level1_Category', 'Level2_Category', 'Level3_Category', 'Level4_Category'])
    
    # Process data rows
    for i, line in enumerate(lines[1:], start=2):
        parts = line.strip().split(',')
        
        # Expected: TopicID, TopicName, Level1, Level2, Level3, Level4 = 6 parts
        # If we have more than 6, some category has an unquoted comma
        
        if len(parts) == 6:
            # Normal case - no issues
            fixed_rows.append(parts)
        elif len(parts) > 6:
            # Issue detected - need to merge extra parts
            issues_found += 1
            
            # First two are always TopicID and TopicName
            topic_id = parts[0]
            topic_name = parts[1]
            
            # Remaining parts need to be intelligently merged back into 4 category fields
            # Strategy: Find parts that start with numbers (like "9.4") - those are category boundaries
            remaining = parts[2:]
            
            categories = []
            current_category = []
            
            for part in remaining:
                # Check if this part starts a new category (begins with digit followed by period)
                if part and len(part) > 1 and part[0].isdigit() and '.' in part[:4]:
                    # This is a new category
                    if current_category:
                        categories.append(', '.join(current_category))
                    current_category = [part]
                else:
                    # Continue building current category
                    current_category.append(part)
            
            # Don't forget the last category
            if current_category:
                categories.append(', '.join(current_category))
            
            # Pad with empty strings to ensure we have 4 category fields
            while len(categories) < 4:
                categories.append('')
            
            # Take only first 4 categories
            categories = categories[:4]
            
            fixed_row = [topic_id, topic_name] + categories
            fixed_rows.append(fixed_row)
            
            if issues_found <= 5:  # Show first 5 examples
                print(f"  Fixed row {i}: {topic_name}")
                print(f"    Original parts: {len(parts)}")
                print(f"    Categories: {categories}")
        else:
            # Fewer than 6 parts - might be missing data, keep as is
            # Pad with empty strings
            while len(parts) < 6:
                parts.append('')
            fixed_rows.append(parts[:6])
    
    print(f"\n✓ Fixed {issues_found} rows with comma issues")
    
    # Write fixed CSV
    print(f"\nWriting {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(fixed_rows)
    
    print(f"✓ Wrote {len(fixed_rows)} rows to {OUTPUT_FILE}")
    print(f"\n✅ Done! Now use {OUTPUT_FILE} as input for the flatten script.")

if __name__ == "__main__":
    fix_csv()
