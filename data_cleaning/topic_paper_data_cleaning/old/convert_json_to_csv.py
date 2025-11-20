"""
Simple script to convert JSON to CSV with paperID and abstract2sentence columns
"""

import json
import csv
import os

def convert_json_to_csv(input_file="thing.json", output_file="paper_abstracts.csv"):
    """
    Convert JSON file to CSV with paperID and abstract2sentence columns
    """
    
    print(f"Converting {input_file} to {output_file}...")
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found")
        return False
    
    # Check file size
    file_size = os.path.getsize(input_file)
    if file_size == 0:
        print(f"❌ Error: {input_file} is empty")
        print("💡 Try saving the file in VS Code again (Ctrl+S)")
        return False
    
    try:
        # Read JSON data
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validate data structure
        if not isinstance(data, list):
            print("❌ Error: JSON should be an array of objects")
            return False
        
        if len(data) == 0:
            print("❌ Error: JSON array is empty")
            return False
        
        # Write CSV file
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow(['paperID', 'abstract2sentence'])
            
            # Write data rows
            for item in data:
                paper_id = item.get('paperID', '')
                abstract = item.get('abstract2sentence', '')
                writer.writerow([paper_id, abstract])
        
        print(f"✅ Success! Created {output_file}")
        print(f"📊 Converted {len(data)} records")
        
        # Show file info
        output_size = os.path.getsize(output_file)
        print(f"📁 Output file size: {output_size:,} bytes")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    convert_json_to_csv()