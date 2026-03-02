"""
Integration tests for ETL pipeline

Tests the complete flow: Parse -> Clean -> Ready for modeling
"""

import pytest
import polars as pl
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.etl.parser import ReportParser
from src.etl.cleaner import DataCleaner, CleanerConfig
from src.context import PipelineContext


class TestETLPipeline:
    """Test complete ETL pipeline"""

    @pytest.fixture(autouse=True)
    def setup_context(self):
        PipelineContext.reset_for_testing()
        ctx = PipelineContext()
        # Initializing with a fixed baseline to avoid future data issues
        ctx.initialize(timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        self.ctx = ctx
        yield
        PipelineContext.reset_for_testing()
    
    def test_parser_initialization(self):
        """Test parser can be initialized"""
        parser = ReportParser()
        assert parser.header_line == 0
    
    def test_cleaner_initialization(self):
        """Test cleaner can be initialized"""
        cleaner = DataCleaner(pipeline_context=self.ctx)
        assert cleaner.config.resample_interval == "5m"
    
    def test_full_clean_flow(self):
        """Test full cleaning flow including wet bulb and resampling via clean()"""
        cleaner = DataCleaner(pipeline_context=self.ctx)
        
        # Create test data
        # Note: In v2.2, clean() expects columns matching the site configuration or defaults
        df = pl.DataFrame({
            'timestamp': pl.datetime_range(
                start=datetime(2024, 1, 1, 10, 0, 0),
                end=datetime(2024, 1, 1, 11, 0, 0, 0),
                interval='1m',
                eager=True
            ),
            'temp_db_out': [25.0] * 61,
            'rh_out': [60.0] * 61,
            'chiller_1_status': [1] * 61,
            'pump_1_status': [1] * 61
        }).with_columns(
            pl.col("timestamp").dt.replace_time_zone("UTC").cast(pl.Datetime("ns", "UTC"))
        )
        
        df_clean, metadata, audit = cleaner.clean(df)
        
        assert len(df_clean) > 0
        assert 'timestamp' in df_clean.columns
        # Should be resampled to 5m intervals
        # 60 mins / 5 = 12 intervals + 1 = 13 rows
        assert len(df_clean) == 13
    
    @pytest.mark.skipif(
        not Path("data/test_sample.csv").exists(),
        reason="Test data not available"
    )
    def test_full_pipeline_with_file(self):
        """Test complete ETL pipeline with actual data via clean()"""
        parser = ReportParser()
        df = parser.parse_file("data/test_sample.csv")
        
        assert len(df) > 0
        assert 'timestamp' in df.columns
        
        cleaner = DataCleaner(pipeline_context=self.ctx)
        df_clean, _, _ = cleaner.clean(df)
        
        assert len(df_clean) > 0
        assert df_clean['timestamp'].is_sorted()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
