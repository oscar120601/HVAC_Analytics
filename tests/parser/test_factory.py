from pathlib import Path
from datetime import datetime, timezone

import polars as pl
import pytest

from src.etl.parser import ParserFactory
from src.etl.parser.base import BaseParser
from src.etl.parser.generic_parser import GenericParser
from src.etl.parser.siemens.scheduler_report import SiemensSchedulerReportParser


class CustomParserStrategy(BaseParser):
    def parse_file(self, file_path, temporal_context=None):
        self._inject_pipeline_origin_timestamp(temporal_context=temporal_context)
        df = pl.DataFrame(
            {
                "timestamp": [datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)],
            }
        )
        df = self._standardize_timezone(df, assumed_tz="UTC")
        self.validate_output(df)
        return df

    def get_metadata(self):
        return dict(self._metadata)


def test_factory_default_strategies():
    strategies = ParserFactory.list_strategies()
    assert "generic" in strategies
    assert "siemens_scheduler" in strategies


def test_factory_create_parser_success():
    parser = ParserFactory.create_parser("generic", config={"assumed_timezone": "UTC"})
    assert isinstance(parser, GenericParser)


def test_factory_create_parser_unknown_type():
    with pytest.raises(ValueError):
        ParserFactory.create_parser("unknown_parser")


def test_factory_register_strategy():
    ParserFactory.register_strategy("test_custom", CustomParserStrategy)
    parser = ParserFactory.create_parser("test_custom")
    assert isinstance(parser, CustomParserStrategy)


def test_auto_detect_siemens(tmp_path: Path):
    content = '\n'.join([
        '"Key            Name:Suffix                                Trend Definitions Used"',
        '"Point_1:","AHWP-3.KWH","","1 hour"',
        '"Time Interval:","15 Minutes"',
        '"Date Range:","2015/12/13 00:00:00 - 2015/12/13 23:59:59"',
        '"Report Timings:","All Hours"',
        '""',
        '"<>Date","Time","Point_1"',
        '"2015/12/13","00:00:00","100"',
    ])
    path = tmp_path / "siemens.csv"
    path.write_text(content, encoding="utf-8")

    parser = ParserFactory.auto_detect(path, config={"assumed_timezone": "UTC"})
    assert isinstance(parser, SiemensSchedulerReportParser)


def test_auto_detect_fallback_generic(tmp_path: Path):
    path = tmp_path / "generic.csv"
    path.write_text("Date,Time,Value\n2026/01/01,00:00:00,1.0\n", encoding="utf-8")
    parser = ParserFactory.auto_detect(path, config={"assumed_timezone": "UTC"})
    assert isinstance(parser, GenericParser)
