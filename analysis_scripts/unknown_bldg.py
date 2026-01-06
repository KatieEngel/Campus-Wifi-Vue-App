import pandas as pd

def find_unique_unknown_ids():
    """
    Loads the unknown buildings summary and prints a list of unique building IDs.
    """
    input_file = 'notebooks/data/unknown_buildings_summary.csv'
    
    try:
        # Load the CSV file
        df = pd.read_csv(input_file)
        
        # Check if the 'BLDG_CODE' column exists
        if 'BLDG_CODE' not in df.columns:
            print(f"Error: Column 'BLDG_CODE' not found in {input_file}.")
            return

        # Get the unique building IDs
        unique_ids = df['building_id'].unique()
        
        print(f"Found {len(unique_ids)} unique building IDs in {input_file}:")
        
        # Print the list
        for building_id in sorted(unique_ids):
            print(building_id)
            
    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
        print("Please run the 'process_data.py' script first to create it.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    find_unique_unknown_ids()