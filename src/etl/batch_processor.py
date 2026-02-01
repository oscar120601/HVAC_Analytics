import polars as pl
import logging
from pathlib import Path
from typing import List, Dict
from tqdm import tqdm

from etl.parser import ReportParser
from etl.cleaner import DataCleaner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BatchProcessor:
    """
    Process multiple CSV report files in batch mode.
    Handles parsing, cleaning, and merging operations.
    """
    
    def __init__(self, resample_interval: str = "5m"):
        self.parser = ReportParser()
        self.cleaner = DataCleaner(resample_interval=resample_interval)
        self.results = []
    
    def process_files(self, file_paths: List[str], clean: bool = True) -> pl.DataFrame:
        """
        Process multiple files and merge into single DataFrame.
        
        Args:
            file_paths: List of absolute paths to CSV files
            clean: Whether to apply cleaning pipeline
        
        Returns:
            Merged DataFrame containing all data
        """
        logger.info(f"Starting batch processing of {len(file_paths)} files")
        
        parsed_dfs = []
        errors = []
        
        for file_path in tqdm(file_paths, desc="Processing files"):
            try:
                # Parse file
                df = self.parser.parse_file(file_path)
                
                # Optionally clean
                if clean:
                    df = self.cleaner.clean_data(df)
                
                parsed_dfs.append(df)
                logger.info(f"✓ Processed: {Path(file_path).name} ({len(df)} rows)")
                
            except Exception as e:
                error_msg = f"✗ Failed: {Path(file_path).name} - {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        if not parsed_dfs:
            raise ValueError("No files were successfully processed")
        
        # Normalize schemas before merging
        logger.info(f"Normalizing schemas for {len(parsed_dfs)} DataFrames...")
        normalized_dfs = []
        
        for df in parsed_dfs:
            # Try to cast string columns that look like numbers to float
            for col in df.columns:
                if df[col].dtype == pl.Utf8:
                    # Try casting to float, if fails keep as string
                    try:
                        df = df.with_columns(
                            pl.col(col).cast(pl.Float64, strict=False)
                        )
                    except:
                        pass  # Keep as string if conversion fails
            normalized_dfs.append(df)
        
        # Merge all DataFrames with schema alignment
        logger.info(f"Merging {len(normalized_dfs)} DataFrames...")
        
        # Use diagonal concat to handle schema variations
        # This will fill missing columns with nulls
        merged_df = pl.concat(normalized_dfs, how="diagonal")
        
        # Sort by timestamp and remove duplicates
        if "timestamp" in merged_df.columns:
            merged_df = merged_df.sort("timestamp")
            # Remove duplicate timestamps (keep first occurrence)
            merged_df = merged_df.unique(subset=["timestamp"], keep="first")
        
        logger.info(f"Batch processing complete: {len(merged_df)} total rows")
        
        if errors:
            logger.warning(f"{len(errors)} files had errors:")
            for err in errors:
                logger.warning(f"  {err}")
        
        return merged_df
    
    def process_directory(self, directory_path: str, 
                          file_pattern: str = "*.csv",
                          clean: bool = True) -> pl.DataFrame:
        """
        Process all CSV files in a directory.
        
        Args:
            directory_path: Path to directory containing CSV files
            file_pattern: Glob pattern for file selection
            clean: Whether to apply cleaning pipeline
        
        Returns:
            Merged DataFrame
        """
        dir_path = Path(directory_path)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        # Find all matching files
        file_paths = sorted([str(f) for f in dir_path.glob(file_pattern)])
        
        if not file_paths:
            raise ValueError(f"No files found matching pattern '{file_pattern}' in {directory_path}")
        
        logger.info(f"Found {len(file_paths)} files in {directory_path}")
        
        return self.process_files(file_paths, clean=clean)

if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        processor = BatchProcessor(resample_interval="5m")
        df = processor.process_directory(sys.argv[1], clean=True)
        print(f"Processed {len(df)} rows")
        print(df.head())
