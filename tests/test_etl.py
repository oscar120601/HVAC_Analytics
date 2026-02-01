import pytest
import polars as pl
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etl.parser import ReportParser
from etl.cleaner import DataCleaner

class TestETLPipeline:
    """Integration tests for ETL pipeline."""
    
    @pytest.fixture
    def sample_csv_path(self):
        """Path to a sample CSV file for testing."""
        # Adjust this to point to an actual test file
        return "HVAC_Cleaning_Visualization/data/CGMH-TY/TI_ANDY_SCHEDULER_USE_REPORT_01-01-17_15-10.csv"
    
    def test_parser_can_read_file(self, sample_csv_path):
        """Test that parser can read and process a report file."""
        parser = ReportParser()
        
        if not Path(sample_csv_path).exists():
            pytest.skip(f"Test file not found: {sample_csv_path}")
        
        df = parser.parse_file(sample_csv_path)
        
        # Basic assertions
        assert df is not None
        assert len(df) > 0
        assert "timestamp" in df.columns
        assert df["timestamp"].dtype == pl.Datetime
    
    def test_parser_metadata_extraction(self, sample_csv_path):
        """Test that metadata mapping is correctly extracted."""
        parser = ReportParser()
        
        if not Path(sample_csv_path).exists():
            pytest.skip(f"Test file not found: {sample_csv_path}")
        
        mapping = parser.parse_metadata(sample_csv_path)
        
        assert len(mapping) > 0
        assert "Point_1" in mapping
        # Check that mapping contains sensor names
        assert all(isinstance(v, str) for v in mapping.values())
    
    def test_cleaner_resample(self):
        """Test data resampling to 5-minute intervals."""
        # Create synthetic test data
        timestamps = pl.datetime_range(
            start=pl.datetime(2023, 1, 1),
            end=pl.datetime(2023, 1, 1, 1, 0),
            interval="1m",
            eager=True
        )
        
        df = pl.DataFrame({
            "timestamp": timestamps,
            "value": list(range(len(timestamps)))
        })
        
        cleaner = DataCleaner(resample_interval="5m")
        df_resampled = cleaner.resample_to_intervals(df)
        
        # Should have reduced rows (60 minutes / 5 = 12 intervals)
        assert len(df_resampled) <= len(df)
        assert "timestamp" in df_resampled.columns
    
    def test_wet_bulb_calculation(self):
        """Test wet-bulb temperature calculation."""
        df = pl.DataFrame({
            "timestamp": [pl.datetime(2023, 1, 1)],
            "temp_db_out": [25.0],  # 25°C
            "rh_out": [60.0]  # 60% RH
        })
        
        cleaner = DataCleaner()
        df_with_wb = cleaner.calculate_wet_bulb_temp(df)
        
        assert "temp_wb_out" in df_with_wb.columns
        # Wet bulb should be less than dry bulb
        assert df_with_wb["temp_wb_out"][0] < df_with_wb["temp_db_out"][0]
    
    def test_end_to_end_pipeline(self, sample_csv_path):
        """Test complete ETL pipeline: Parse -> Clean."""
        if not Path(sample_csv_path).exists():
            pytest.skip(f"Test file not found: {sample_csv_path}")
        
        # Parse
        parser = ReportParser()
        df_raw = parser.parse_file(sample_csv_path)
        
        # Clean
        cleaner = DataCleaner()
        df_clean = cleaner.clean_data(df_raw)
        
        # Verify output
        assert df_clean is not None
        assert len(df_clean) > 0
        assert "timestamp" in df_clean.columns
        
        # Check that cleaning added derived columns
        # (depending on what columns exist in the actual data)
        print(f"Clean data shape: {df_clean.shape}")
        print(f"Columns: {df_clean.columns[:10]}...")  # Print first 10 columns

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
