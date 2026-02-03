import polars as pl
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReportParser:
    """
    Parses 'TI_ANDY_SCHEDULER_USE_REPORT' CSV files.
    Format:
      - Lines 1-N: Metadata mapping (Point_ID -> Sensor_Name)
      - Line N+1: Data header ("<>Date", "Time", "Point_1", ...)
      - Line N+2+: Data rows
      
    The parser auto-detects where metadata ends and data begins.
    """
    
    def __init__(self):
        self.point_map: Dict[str, str] = {}
        self.header_line: int = 0  # Line number of the data header (0-indexed)
    
    def _find_header_line(self, file_path: str) -> int:
        """
        Finds the line number containing the data header ('<>Date').
        Returns 0-indexed line number.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                for i, line in enumerate(f):
                    if line.startswith('"<>Date"') or line.startswith('<>Date'):
                        logger.info(f"Found data header at line {i + 1} (1-indexed)")
                        return i
            
            # Fallback to default if not found
            logger.warning(f"Could not find '<>Date' header, using default line 211")
            return 211
        except Exception as e:
            logger.error(f"Error finding header line: {e}")
            return 211
    
    def parse_metadata(self, file_path: str, max_lines: int) -> Dict[str, str]:
        """Extracts Point_ID to Sensor_Name mapping from the file header."""
        mapping = {}
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
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

        # 1. Auto-detect header line
        self.header_line = self._find_header_line(file_path)
        
        # 2. Parse Metadata (all lines before header)
        self.point_map = self.parse_metadata(file_path, self.header_line)
        
        # 3. Read Data Section
        try:
            df = pl.read_csv(
                file_path,
                skip_rows=self.header_line,
                infer_schema_length=1000,
                encoding='utf-8',
                null_values=["", "NA", "null"],
                ignore_errors=True,
                truncate_ragged_lines=True  # Handle lines with extra/missing fields
            )
            
            # Filter out separator lines (e.g. "**********")
            if "<>Date" in df.columns:
                df = df.filter(~pl.col("<>Date").str.starts_with("*"))
            
            # 4. Clean Column Names
            # Standardize "<>Date" to "Date"
            if "<>Date" in df.columns:
                df = df.rename({"<>Date": "Date"})
            
            # 5. Apply Mapping to Point Columns
            rename_dict = {}
            for col in df.columns:
                if col in self.point_map:
                    # Clean the sensor name
                    original_name = self.point_map[col]
                    clean_name = original_name.replace("-", "_").replace(".", "_").replace(":", "_")
                    rename_dict[col] = clean_name
            
            if rename_dict:
                df = df.rename(rename_dict)
            
            # 6. Merge Date and Time into Timestamp
            if "Date" in df.columns and "Time" in df.columns:
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

