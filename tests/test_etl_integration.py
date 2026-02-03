"""
Integration tests for ETL pipeline

Tests the complete flow: Parse -> Clean -> Ready for modeling
"""

import pytest
import polars as pl
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.etl.parser import ReportParser
from src.etl.cleaner import DataCleaner


class TestETLPipeline:
    """Test complete ETL pipeline"""
    
    def test_parser_initialization(self):
        """Test parser can be initialized"""
        parser = ReportParser()
        assert parser.metadata_lines == 211
    
    def test_cleaner_initialization(self):
        """Test cleaner can be initialized"""
        cleaner = DataCleaner()
        assert cleaner.resample_interval == "5m"
    
    def test_wet_bulb_calculation(self):
        """Test wet bulb temperature calculation"""
        cleaner = DataCleaner()
        
        # Create test data
        df = pl.DataFrame({
            'timestamp': pl.datetime_range(
                start=pl.datetime(2024, 1, 1),
                end=pl.datetime(2024, 1, 1, 1),
                interval='5m',
                eager=True
            ),
            'temp_db_out': [85.0] * 13,
            'rh_out': [60.0] * 13
        })
        
        df_with_wb = cleaner.calculate_wet_bulb_temp(df)
        
        assert 'temp_wb_out' in df_with_wb.columns
        assert df_with_wb['temp_wb_out'].null_count() == 0
        
        # Wet bulb should be less than dry bulb
        assert (df_with_wb['temp_wb_out'] < df_with_wb['temp_db_out']).all()
    
    def test_frozen_data_detection(self):
        """Test frozen data detection"""
        cleaner = DataCleaner()
        
        # Create data with frozen section
        values = [100.0] * 10 + [110.0, 120.0, 130.0]
        df = pl.DataFrame({
            'timestamp': pl.datetime_range(
                start=pl.datetime(2024, 1, 1),
                end=pl.datetime(2024, 1, 1, 1),
                interval='5m',
                eager=True
            ),
            'sensor_value': values
        })
        
        df_flagged = cleaner.detect_frozen_data(df, 'sensor_value', window=6)
        
        assert 'sensor_value_frozen' in df_flagged.columns
        # First 10 values should be flagged as frozen
        frozen_count = df_flagged['sensor_value_frozen'].sum()
        assert frozen_count > 0
    
    def test_resample_to_intervals(self):
        """Test resampling to 5-minute intervals"""
        cleaner = DataCleaner(resample_interval="5m")
        
        # Create 1-minute data
        df = pl.DataFrame({
            'timestamp': pl.datetime_range(
                start=pl.datetime(2024, 1, 1),
                end=pl.datetime(2024, 1, 1, 0, 30),
                interval='1m',
                eager=True
            ),
            'value': range(31)
        })
        
        df_resampled = cleaner.resample_to_intervals(df)
        
        # Should have ~6 rows (0, 5, 10, 15, 20, 25 minutes)
        assert len(df_resampled) == 7  # Including 0 and 30
        assert df_resampled['timestamp'].is_sorted()
    
    @pytest.mark.skipif(
        not Path("data/test_sample.csv").exists(),
        reason="Test data not available"
    )
    def test_full_pipeline(self):
        """Test complete ETL pipeline with actual data"""
        # This test requires a sample CSV file
        parser = ReportParser()
        df = parser.parse_file("data/test_sample.csv")
        
        assert len(df) > 0
        assert 'timestamp' in df.columns
        
        cleaner = DataCleaner()
        df_clean = cleaner.clean_data(df)
        
        assert len(df_clean) > 0
        assert df_clean['timestamp'].is_sorted()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
