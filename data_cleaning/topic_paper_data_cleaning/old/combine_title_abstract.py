import csv
import os

def combine_title_and_abstract():
    """
    Combines paper titles and abstracts from two CSV files:
    - Reads titles from extract_paper_abstract.csv
    - Reads abstracts from paper_abstracts.csv
    - Creates combined summaries with format: "Title; Abstract"
    - Outputs to paper_summary.csv with columns: paperID, paper_summary
    """
    
    # File paths
    titles_file = 'extract_paper_abstract.csv'
    abstracts_file = 'paper_abstracts.csv'
    output_file = 'paper_summary.csv'
    
    # Check if input files exist
    if not os.path.exists(titles_file):
        print(f"Error: {titles_file} not found!")
        return
    
    if not os.path.exists(abstracts_file):
        print(f"Error: {abstracts_file} not found!")
        return
    
    # Read titles into a dictionary (paperID -> title)
    titles_dict = {}
    print(f"Reading titles from {titles_file}...")
    
    try:
        with open(titles_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                paper_id = row.get('paperID', '').strip()
                title = row.get('title', '').strip()
                if paper_id and title:
                    titles_dict[paper_id] = title
        
        print(f"Successfully loaded {len(titles_dict)} titles")
    
    except Exception as e:
        print(f"Error reading {titles_file}: {e}")
        return
    
    # Read abstracts and combine with titles
    combined_data = []
    print(f"Reading abstracts from {abstracts_file}...")
    
    try:
        with open(abstracts_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                paper_id = row.get('paperID', '').strip()
                abstract = row.get('abstract2sentence', '').strip()
                
                if paper_id:
                    # Get the corresponding title
                    title = titles_dict.get(paper_id, '')
                    
                    # Create combined summary
                    if title and abstract:
                        paper_summary = f"{title}; {abstract}"
                    elif title and not abstract:
                        paper_summary = title  # Just title if no abstract
                    elif not title and abstract:
                        paper_summary = abstract  # Just abstract if no title
                    else:
                        paper_summary = ''  # Empty if both missing
                    
                    combined_data.append({
                        'paperID': paper_id,
                        'paper_summary': paper_summary
                    })
        
        print(f"Successfully processed {len(combined_data)} papers")
    
    except Exception as e:
        print(f"Error reading {abstracts_file}: {e}")
        return
    
    # Write combined data to output file
    print(f"Writing combined data to {output_file}...")
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['paperID', 'paper_summary']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # Write header
            writer.writeheader()
            
            # Write data
            writer.writerows(combined_data)
        
        print(f"Successfully created {output_file} with {len(combined_data)} entries")
        
        # Show statistics
        titles_found = sum(1 for row in combined_data if titles_dict.get(row['paperID'], ''))
        abstracts_found = sum(1 for row in combined_data if ';' in row['paper_summary'])
        both_found = sum(1 for row in combined_data if titles_dict.get(row['paperID'], '') and ';' in row['paper_summary'])
        
        print("\nStatistics:")
        print(f"Papers with titles: {titles_found}")
        print(f"Papers with both title and abstract: {both_found}")
        print(f"Papers with only title: {titles_found - both_found}")
        print(f"Papers with only abstract: {len(combined_data) - titles_found}")
        
        # Show a few examples
        print("\nFirst 3 examples:")
        for i, row in enumerate(combined_data[:3]):
            if row['paper_summary']:
                print(f"{i+1}. ID {row['paperID']}: {row['paper_summary'][:100]}...")
    
    except Exception as e:
        print(f"Error writing {output_file}: {e}")
        return

if __name__ == "__main__":
    combine_title_and_abstract()