import pytest
import polars as pl
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etl.parser import ReportParser
from etl.cleaner import DataCleaner, CleanerConfig
from context import PipelineContext

class TestETLPipeline:
    """Integration tests for ETL pipeline."""
    
    @pytest.fixture(autouse=True)
    def setup_context(self):
        PipelineContext.reset_for_testing()
        ctx = PipelineContext()
        ctx.initialize(timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        self.ctx = ctx
        yield
        PipelineContext.reset_for_testing()

    @pytest.fixture
    def sample_csv_path(self):
        """Path to a sample CSV file for testing."""
        return "HVAC_Cleaning_Visualization/data/CGMH-TY/TI_ANDY_SCHEDULER_USE_REPORT_01-01-17_15-10.csv"
    
    def test_parser_can_read_file(self, sample_csv_path):
        """Test that parser can read and process a report file."""
        parser = ReportParser()
        
        if not Path(sample_csv_path).exists():
            pytest.skip(f"Test file not found: {sample_csv_path}")
        
        df = parser.parse_file(sample_csv_path)
        
        assert df is not None
        assert len(df) > 0
        assert "timestamp" in df.columns
    
    def test_clean_flow_integration(self):
        """Test the integration of resampling and cleaning via the public clean() method."""
        timestamps = pl.datetime_range(
            start=datetime(2023, 1, 1, 10, 0, 0),
            end=datetime(2023, 1, 1, 11, 0, 0),
            interval="1m",
            eager=True
        )
        
        df = pl.DataFrame({
            "timestamp": timestamps,
            "chiller_1_kw": [100.0] * len(timestamps),
            "chiller_1_status": [1] * len(timestamps),
            "pump_1_status": [1] * len(timestamps)
        }).with_columns(
            pl.col("timestamp").dt.replace_time_zone("UTC").cast(pl.Datetime("ns", "UTC"))
        )
        
        cleaner = DataCleaner(pipeline_context=self.ctx)
        df_clean, _, _ = cleaner.clean(df)
        
        # 60 mins -> 13 rows (0, 5, ..., 60)
        assert len(df_clean) == 13
        assert "timestamp" in df_clean.columns
    
    def test_end_to_end_pipeline(self, sample_csv_path):
        """Test complete ETL pipeline: Parse -> Clean."""
        if not Path(sample_csv_path).exists():
            pytest.skip(f"Test file not found: {sample_csv_path}")
        
        # Parse
        parser = ReportParser()
        df_raw = parser.parse_file(sample_csv_path)
        
        # Clean
        cleaner = DataCleaner(pipeline_context=self.ctx)
        df_clean, metadata, audit = cleaner.clean(df_raw)
        
        assert df_clean is not None
        assert len(df_clean) > 0
        assert "timestamp" in df_clean.columns
        assert df_clean["timestamp"].dtype.time_zone == "UTC"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
