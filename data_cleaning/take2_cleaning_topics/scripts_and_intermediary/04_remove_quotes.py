"""
Script to remove quotation marks from TopicNode_Deduplicated.csv
"""

import csv

def remove_quotes():
    input_file = 'TopicNode_Deduplicated.csv'
    output_file = 'TopicNode_NoQuotes.csv'
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.DictReader(infile)
        
        # Write header manually
        outfile.write('Id,Name\n')
        
        for row in reader:
            # Write each row manually without quotes
            # Just concatenate Id and Name with a comma
            topic_id = row['Id']
            topic_name = row['Name']
            outfile.write(f'{topic_id},{topic_name}\n')
    
    print(f"Removed quotation marks and created clean CSV")
    print(f"Output saved to {output_file}")

if __name__ == "__main__":
    remove_quotes()
