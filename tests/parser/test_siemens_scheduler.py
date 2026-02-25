from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.context import PipelineContext
from src.etl.parser import ParserFactory


def _build_siemens_sample(point_rows: list[str], data_rows: list[str]) -> str:
    return "\n".join(
        [
            '"Key            Name:Suffix                                Trend Definitions Used"',
            *point_rows,
            '"Time Interval:","15 Minutes"',
            '"Date Range:","2015/12/13 00:00:00 - 2015/12/13 23:59:59"',
            '"Report Timings:","All Hours"',
            '""',
            '"<>Date","Time","Point_1","Point_2"',
            *data_rows,
        ]
    )


def test_siemens_parser_point_mapping_and_metadata(tmp_path: Path):
    content = _build_siemens_sample(
        point_rows=[
            '"Point_1:","AHWP-3.KWH","","1 hour"',
            '"Point_2:","CH-1-CH.WDP","","1 hour"',
        ],
        data_rows=[
            '"2015/12/13","00:00:00","127316","8.5"',
            '"2015/12/13","01:00:00","127400","9.1"',
        ],
    )
    path = tmp_path / "cgmh.csv"
    path.write_text(content, encoding="utf-8")

    PipelineContext.reset_for_testing()
    ctx = PipelineContext()
    baseline = datetime(2026, 2, 25, 0, 0, 0, tzinfo=timezone.utc)
    ctx.initialize(timestamp=baseline, site_id="cgmh_ty")

    parser = ParserFactory.create_parser(
        "siemens_scheduler",
        config={"assumed_timezone": "Asia/Taipei"},
    )
    df = parser.parse_file(path, temporal_context=ctx)
    metadata = parser.get_metadata()

    assert "timestamp" in df.columns
    assert "ahwp_3_kwh" in df.columns
    assert "ch_1_ch_wdp" in df.columns
    assert str(df["timestamp"].dtype.time_zone) == "UTC"
    assert df["timestamp"].dtype.time_unit == "ns"
    assert metadata["pipeline_origin_timestamp"] == baseline.isoformat()
    assert "Point_1" in metadata["point_mapping"]
    assert metadata["point_mapping"]["Point_1"]["normalized_name"] == "ahwp_3_kwh"


def test_siemens_parser_kmuh_style_small_points(tmp_path: Path):
    content = _build_siemens_sample(
        point_rows=[
            '"Point_1:","MMCB.KW","","5 minutes"',
            '"Point_2:","MMCB.TA","","5 minutes"',
        ],
        data_rows=['"2016/10/10","00:00:00","4583","21.5"'],
    )
    path = tmp_path / "kmuh.csv"
    path.write_text(content, encoding="utf-8")

    parser = ParserFactory.create_parser(
        "siemens_scheduler",
        config={"assumed_timezone": "Asia/Taipei"},
    )
    df, metadata = parser.parse_with_metadata(path)

    assert df.height == 1
    assert "mmcb_kw" in df.columns
    assert metadata["point_mapping"]["Point_2"]["normalized_name"] == "mmcb_ta"


def test_siemens_parser_missing_header_raises(tmp_path: Path):
    bad_content = '\n'.join(
        [
            '"Point_1:","AHWP-3.KWH","","1 hour"',
            '"Date Range:","2015/12/13 00:00:00 - 2015/12/13 23:59:59"',
            '"2015/12/13","00:00:00","127316"',
        ]
    )
    path = tmp_path / "bad.csv"
    path.write_text(bad_content, encoding="utf-8")

    parser = ParserFactory.create_parser("siemens_scheduler")
    with pytest.raises(Exception) as exc:
        parser.parse_file(path)
    assert "E104" in str(exc.value)

