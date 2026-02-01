import polars as pl
import logging
from pathlib import Path
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReportParser:
    """
    Parses 'TI_ANDY_SCHEDULER_USE_REPORT' CSV files.
    Format:
      - Lines 1-211: Metadata mapping (Point_ID -> Sensor_Name)
      - Line 212+: Data header ("<>Date", "Time", "Point_1", ...)
    """
    
    def __init__(self, metadata_lines: int = 211):
        self.metadata_lines = metadata_lines
        self.point_map: Dict[str, str] = {}
    
    def parse_metadata(self, file_path: str) -> Dict[str, str]:
        """Extracts Point_ID to Sensor_Name mapping from the file header."""
        mapping = {}
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                for i, line in enumerate(f):
                    if i >= self.metadata_lines:
                        break
                    
                    # Expected line format: "Point_1:","AHWP-3.KWH","","1 hour"
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        # Extract "Point_1" from "Point_1:"
                        point_id = parts[0].strip().strip('"').replace(':', '')
                        # Extract "AHWP-3.KWH"
                        sensor_name = parts[1].strip().strip('"')
                        
                        if point_id.startswith("Point_") and sensor_name:
                            mapping[point_id] = sensor_name
                            
            logger.info(f"Extracted {len(mapping)} point mappings from {file_path}")
            return mapping
        except Exception as e:
            logger.error(f"Error parsing metadata: {e}")
            raise

    def parse_file(self, file_path: str) -> pl.DataFrame:
        """Reads the full report and returns a processed DataFrame."""
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # 1. Parse Metadata first
        self.point_map = self.parse_metadata(file_path)
        
        # 2. Read Data Section
        # Skip metadata lines. The header is effectively at line 212 (0-indexed logic depends on reader)
        # We use polars scan_csv or read_csv with skip_rows
        try:
            # Note: Polars `skip_rows` skips the first N rows. 
            # If data header is at line 212 (1-indexed), we actully need to skip 211 lines?
            # Let's verify: In `head -n 212 ...` output from previous turn:
            # Line 212 is: "<>Date","Time","Point_1"...
            # So we skip 211 lines.
            
            df = pl.read_csv(
                file_path,
                skip_rows=211,
                infer_schema_length=1000,
                encoding='utf-8',
                null_values=["", "NA", "null"],
                ignore_errors=True # Handle potential formatting glitches
            )
            
            # 3. Clean Column Names
            # Standardize "<>Date" to "Date"
            df = df.rename({"<>Date": "Date"})
            
            # 4. Apply Mapping to Point Columns
            rename_dict = {}
            for col in df.columns:
                if col in self.point_map:
                    # Clean the sensor name to be snake_case compatible if needed, 
                    # but for now keeping original name is safer for traceability, 
                    # or we sanitize it: "AHWP-3.KWH" -> "AHWP_3_KWH"
                    original_name = self.point_map[col]
                    clean_name = original_name.replace("-", "_").replace(".", "_").replace(":", "_")
                    rename_dict[col] = clean_name
            
            if rename_dict:
                df = df.rename(rename_dict)
            
            # 5. Merge Date and Time into Timestamp
            if "Date" in df.columns and "Time" in df.columns:
                # Polars string parsing to datetime
                # Date format: 2017/01/01
                # Time format: 15:10:00
                
                df = df.with_columns(
                    (pl.col("Date") + " " + pl.col("Time"))
                    .str.strptime(pl.Datetime, format="%Y/%m/%d %H:%M:%S")
                    .alias("timestamp")
                )
                
                # Sort by timestamp
                df = df.sort("timestamp")
            
            logger.info(f"Successfully parsed {file_path}: {df.shape[0]} rows, {df.shape[1]} columns")
            return df

        except Exception as e:
            logger.error(f"Error parsing data section: {e}")
            raise

if __name__ == "__main__":
    # Smoke test
    import sys
    if len(sys.argv) > 1:
        parser = ReportParser()
        df = parser.parse_file(sys.argv[1])
        print(df.head())
        print(df.schema)
