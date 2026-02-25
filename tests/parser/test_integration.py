from datetime import datetime, timezone
from pathlib import Path

from src.context import PipelineContext
from src.etl.cleaner import DataCleaner
from src.etl.parser import ParserFactory


def test_siemens_to_cleaner_integration(tmp_path: Path):
    content = "\n".join(
        [
            '"Key            Name:Suffix                                Trend Definitions Used"',
            '"Point_1:","AHWP-3.KWH","","15 minutes"',
            '"Point_2:","AHWP-4.KWH","","15 minutes"',
            '"Time Interval:","15 Minutes"',
            '"Date Range:","2015/12/13 00:00:00 - 2015/12/13 01:00:00"',
            '"Report Timings:","All Hours"',
            '""',
            '"<>Date","Time","Point_1","Point_2"',
            '"2015/12/13","00:00:00","100","200"',
            '"2015/12/13","00:15:00","110","210"',
        ]
    )
    csv_path = tmp_path / "siemens.csv"
    csv_path.write_text(content, encoding="utf-8")

    PipelineContext.reset_for_testing()
    ctx = PipelineContext()
    ctx.initialize(timestamp=datetime(2026, 2, 25, 12, 0, 0, tzinfo=timezone.utc), site_id="cgmh_ty")

    parser = ParserFactory.create_parser(
        "siemens_scheduler",
        config={"assumed_timezone": "Asia/Taipei"},
    )
    df_parsed, parse_meta = parser.parse_with_metadata(csv_path, temporal_context=ctx)

    cleaner = DataCleaner(pipeline_context=ctx)
    df_clean, metadata, audit = cleaner.clean(df_parsed, input_metadata=parse_meta)

    assert "timestamp" in df_clean.columns
    assert str(df_clean["timestamp"].dtype.time_zone) == "UTC"
    assert "ahwp_3_kwh" in df_clean.columns
    assert "ahwp_4_kwh" in df_clean.columns
    assert isinstance(metadata, dict)
    assert isinstance(audit, dict)

