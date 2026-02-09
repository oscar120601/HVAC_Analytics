import polars as pl
import logging
import sys
from pathlib import Path
from typing import List, Dict

from etl.parser import ReportParser
from etl.cleaner import DataCleaner

# Try to import tqdm, but handle Streamlit environment gracefully
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    
def get_progress_iterator(iterable, desc="Processing", disable=False):
    """Get a progress iterator that works in both CLI and Streamlit environments."""
    # Check if running in Streamlit
    try:
        import streamlit as st
        # If streamlit is imported and we have a runtime, disable tqdm
        if hasattr(st, 'runtime'):
            disable = True
    except:
        pass
    
    if TQDM_AVAILABLE and not disable:
        return tqdm(iterable, desc=desc, file=sys.stdout)
    else:
        # Simple fallback without progress bar
        logger.info(f"{desc}: {len(iterable) if hasattr(iterable, '__len__') else 'unknown'} items")
        return iterable

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
        
        for file_path in get_progress_iterator(file_paths, desc="Processing files"):
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
        
        # First pass: collect all columns and their types across all dataframes
        all_columns = {}
        for df in parsed_dfs:
            for col in df.columns:
                if col not in all_columns:
                    all_columns[col] = set()
                all_columns[col].add(df[col].dtype)
        
        # Determine target types: prioritize numeric types over strings
        # Skip timestamp column - keep it as Datetime
        target_types = {}
        for col, types in all_columns.items():
            # Skip timestamp column - handled separately
            if col == 'timestamp':
                continue
            
            # Check if any type is Float64 or Utf8 (string)
            has_float = any('Float' in str(t) for t in types)
            has_int = any('Int' in str(t) for t in types)
            has_string = pl.Utf8 in types
            
            # PRIORITY: Numeric types take precedence over strings
            # If any file has this column as Float, use Float64
            # If any file has this column as Int (but not Float), use Float64 for safety
            # Only keep as string if NO numeric types are found
            if has_float:
                target_types[col] = pl.Float64
            elif has_int:
                target_types[col] = pl.Float64  # Convert Int to Float64 for consistency
            elif has_string:
                target_types[col] = pl.Utf8  # Only string if no numeric types found
            else:
                target_types[col] = pl.Float64  # Default to Float64 for unknown types
        
        logger.info(f"Target schema: {len(target_types)} columns")
        
        # Second pass: cast all columns to target types (skip timestamp)
        for df in parsed_dfs:
            for col, target_type in target_types.items():
                if col in df.columns:
                    current_type = df[col].dtype
                    if current_type != target_type:
                        try:
                            df = df.with_columns(
                                pl.col(col).cast(target_type, strict=False)
                            )
                            logger.debug(f"Cast {col} from {current_type} to {target_type}")
                        except Exception as e:
                            logger.warning(f"Failed to cast {col}: {e}")
                else:
                    # Add missing column with null values
                    df = df.with_columns(pl.lit(None).cast(target_type).alias(col))
            normalized_dfs.append(df)
        
        # Log timestamp column info for debugging
        if normalized_dfs and 'timestamp' in normalized_dfs[0].columns:
            logger.info(f"Timestamp dtype: {normalized_dfs[0]['timestamp'].dtype}")
        
        # Merge all DataFrames with schema alignment
        logger.info(f"Merging {len(normalized_dfs)} DataFrames...")
        
        # Use diagonal concat to handle schema variations
        # This will fill missing columns with nulls
        try:
            merged_df = pl.concat(normalized_dfs, how="diagonal")
        except Exception as e:
            logger.error(f"Diagonal concat failed: {e}, trying relaxed mode...")
            # If diagonal fails, try relaxed mode which is more lenient
            merged_df = pl.concat(normalized_dfs, how="diagonal_relaxed")
        
        # Sort by timestamp and remove duplicates
        if "timestamp" in merged_df.columns:
            merged_df = merged_df.sort("timestamp")
            # Remove duplicate timestamps (keep first occurrence)
            merged_df = merged_df.unique(subset=["timestamp"], keep="first")
        
        # FINAL TYPE ENFORCEMENT: Ensure all numeric columns are Float64
        # This handles cases where string values like "334.0" need to be converted to 334.0
        logger.info("Enforcing numeric types on all non-timestamp columns...")
        numeric_columns = [col for col in merged_df.columns if col != 'timestamp']
        
        for col in numeric_columns:
            current_type = merged_df[col].dtype
            if current_type != pl.Float64:
                try:
                    # Cast to Float64, invalid values become null
                    merged_df = merged_df.with_columns(
                        pl.col(col).cast(pl.Float64, strict=False)
                    )
                    logger.debug(f"Final cast {col} from {current_type} to Float64")
                except Exception as e:
                    logger.warning(f"Could not cast {col} to Float64: {e}")
        
        # Log final schema summary
        float_count = sum(1 for col in numeric_columns if merged_df[col].dtype == pl.Float64)
        logger.info(f"Final schema: {float_count}/{len(numeric_columns)} columns are Float64")
        
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
