import pandas as pd
import os
import glob
import re

def parse_bas_csv(file_path):
    """
    Parses a single BAS CSV file which has a metadata section followed by pivoted data.
    Returns a DataFrame with renamed columns and timestamp index.
    """
    try:
        # 1. Read the file to locate the data header and parse metadata
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        data_start_line = 0
        point_map = {}
        
        # Regex to capture "Point_X" and the associated Tag Name (e.g., "AH01-1.CV")
        # Example line: "Point_1:","AH-B4-1.CV","","15 minutes"
        # Adjusted regex to be more flexible with quotes and whitespace
        point_pattern = re.compile(r'\"(Point_\d+):\",\"([^\"]+)\"')

        for i, line in enumerate(lines):
            # Check for data header start
            if line.startswith('"<>Date"') or line.startswith('<>Date'):
                data_start_line = i
                break
            
            # Parse metadata lines to build mapping
            match = point_pattern.search(line)
            if match:
                point_id = match.group(1)  # e.g., Point_1
                tag_name = match.group(2)  # e.g., AH-B4-1.CV
                point_map[point_id] = tag_name

        if data_start_line == 0 and len(point_map) == 0:
            print(f"Warning: Could not parse format for {file_path}")
            return None

        # 2. Read the actual data section
        # The header is at data_start_line
        df = pd.read_csv(file_path, skiprows=data_start_line)
        
        # 3. Rename columns using the point_map
        # The CSV header has "Point_1", "Point_2" etc.
        # We need to map them to the tag names found in metadata.
        df.rename(columns=point_map, inplace=True)

        # 4. Create Timestamp Index
        # Combine distinct Date and Time columns if they exist
        if '<>Date' in df.columns and 'Time' in df.columns:
            date_col = '<>Date'
        elif 'Date' in df.columns and 'Time' in df.columns:
            date_col = 'Date'
        else:
            print(f"Error: Date/Time columns not found in {file_path}")
            return None

        # Combine and parse datetime
        df['timestamp'] = pd.to_datetime(df[date_col].astype(str) + ' ' + df['Time'].astype(str), errors='coerce')
        
        # Set index and drop original date/time columns
        df.set_index('timestamp', inplace=True)
        df.drop(columns=[date_col, 'Time'], inplace=True)
        
        # 5. Clean "No Data" and convert to numeric
        # Replace "No Data" with NaN
        df.replace(['No Data', 'no data', 'No data'], float('nan'), inplace=True)
        
        # Convert all columns to numeric, coercing errors
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None

def merge_datasets(data_dir):
    """
    Scans the directory for matching CSV files, parses them, and merges into a single DataFrame.
    """
    all_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not all_files:
        print(f"No csv files found in {data_dir}")
        return None

    merged_df = pd.DataFrame()
    
    print(f"Found {len(all_files)} files to process...")

    for file in all_files:
        print(f"Processing {os.path.basename(file)}...")
        df = parse_bas_csv(file)
        
        if df is not None and not df.empty:
            if merged_df.empty:
                merged_df = df
            else:
                # Merge based on timestamp index (outer join to keep all timepoints)
                # Suffixes might be needed if tag names overlap, but usually BAS tags are unique per point
                merged_df = merged_df.join(df, how='outer', rsuffix='_dup')
    
    # Remove duplicate columns if any (rare in this context unless files overlap)
    # If '_dup' columns exist, we might want to handle them, but for now let's keep them distinct
    
    print(f"Merge complete. Final shape: {merged_df.shape}")
    return merged_df

if __name__ == "__main__":
    # Test path - adjust as needed
    DATA_DIR = os.path.join("data", "Farglory_O3")
    
    # Ensure raw output directory exists
    os.makedirs("output", exist_ok=True)

    df = merge_datasets(DATA_DIR)
    
    if df is not None:
        output_path = os.path.join("output", "raw_merged_data.csv")
        df.to_csv(output_path)
        print(f"Saved merged data to {output_path}")
        print(df.head())
        print(df.info())
