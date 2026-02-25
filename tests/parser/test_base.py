from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest

from src.context import PipelineContext
from src.etl.parser.base import BaseParser
from src.exceptions import ContractViolationError


class DummyParser(BaseParser):
    def parse_file(self, file_path, temporal_context=None):
        self._inject_pipeline_origin_timestamp(temporal_context=temporal_context)
        df = pl.DataFrame(
            {
                "timestamp_raw": ["2026/01/01 00:00:00"],
                "value": [1.0],
            }
        ).with_columns(
            pl.col("timestamp_raw")
            .str.strptime(pl.Datetime, format="%Y/%m/%d %H:%M:%S", strict=False)
            .alias("timestamp")
        ).drop("timestamp_raw")

        df = self._standardize_timezone(df, assumed_tz="UTC")
        self.validate_output(df)
        self._metadata["encoding"] = "utf-8"
        return df

    def get_metadata(self):
        return dict(self._metadata)


def test_base_parser_is_abstract():
    with pytest.raises(TypeError):
        BaseParser()  # type: ignore[abstract]


def test_validate_output_requires_timestamp():
    parser = DummyParser()
    df = pl.DataFrame({"value": [1.0]})
    with pytest.raises(ContractViolationError) as exc:
        parser.validate_output(df)
    assert "E103" in str(exc.value)


def test_metadata_contains_pipeline_origin_timestamp():
    PipelineContext.reset_for_testing()
    ctx = PipelineContext()
    baseline = datetime(2026, 2, 1, 8, 0, 0, tzinfo=timezone.utc)
    ctx.initialize(timestamp=baseline, site_id="test_site")

    parser = DummyParser()
    parser.parse_file(Path("dummy.csv"), temporal_context=ctx)
    metadata = parser.get_metadata()
    assert metadata["pipeline_origin_timestamp"] == baseline.isoformat()
