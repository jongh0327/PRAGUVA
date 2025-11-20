"""
Script to extract only paperID, title, and abstract columns from PaperNode.csv
Creates a new CSV file with these three columns only.
"""

import csv
import os

def extract_paper_essentials():
    # Define file paths
    input_file = 'extract_paper_abstract.csv'
    output_file = 'id_abstract.csv'
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found in current directory.")
        return
    
    try:
        # Read the original CSV and extract only required columns
        with open(input_file, 'r', encoding='utf-8', newline='') as infile, \
             open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            
            reader = csv.DictReader(infile)
            
            # Define the columns we want to keep
            fieldnames = ['paperID', 'title', 'abstract']
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            
            # Write header
            writer.writeheader()
            
            # Track statistics
            total_rows = 0
            rows_with_missing_data = 0
            
            # Process each row
            for row in reader:
                total_rows += 1
                
                # Extract only the required fields
                extracted_row = {
                    'paperID': row.get('paperID', ''),
                    'title': row.get('title', ''),
                    'abstract': row.get('abstract', '')
                }
                
                # Check for missing data (optional - for reporting)
                if not extracted_row['title'] or not extracted_row['abstract']:
                    rows_with_missing_data += 1
                
                # Write the row
                writer.writerow(extracted_row)
        
        # Report results
        print(f"✅ Successfully created {output_file}")
        print(f"📊 Total rows processed: {total_rows}")
        print(f"⚠️  Rows with missing title or abstract: {rows_with_missing_data}")
        
        # Show file sizes for comparison
        input_size = os.path.getsize(input_file) / (1024 * 1024)  # MB
        output_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
        print(f"📁 Input file size: {input_size:.2f} MB")
        print(f"📁 Output file size: {output_size:.2f} MB")
        print(f"💾 Space saved: {input_size - output_size:.2f} MB ({((input_size - output_size) / input_size * 100):.1f}%)")
        
    except Exception as e:
        print(f"❌ Error processing files: {str(e)}")

if __name__ == "__main__":
    print("🔄 Extracting paperID, title, and abstract from PaperNode.csv...")
    extract_paper_essentials()