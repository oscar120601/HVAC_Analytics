from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union
import re

import polars as pl

from src.context import PipelineContext
from src.exceptions import DataValidationError, HeaderValidationError

from ..base import BaseParser
from ..exceptions import MetadataIncompleteError, PointMappingError
from ..utils import DEFAULT_SITE_CONFIG, NULL_VALUES, deep_merge_dict
from .point_mapping import PointMappingManager


class SiemensSchedulerReportParser(BaseParser):
    """
    Parser for Siemens Scheduler report CSV format.

    Typical structure:
    - Point definition section (Point_1 ... Point_N)
    - Metadata section (Time Interval / Date Range / Report Timings)
    - Data header starts with "<>Date","Time","Point_1"... columns
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        merged = deep_merge_dict(DEFAULT_SITE_CONFIG, config or {})
        super().__init__(merged)
        point_overrides = merged.get("point_mapping", {})
        self.point_manager = PointMappingManager(overrides=point_overrides)
        self._file_metadata: Dict[str, Any] = {}

    def get_metadata(self) -> Dict[str, Any]:
        return {
            **self._metadata,
            **self._file_metadata,
            "point_mapping": self.point_manager.get_point_metadata(),
            "parser_type": "siemens_scheduler",
        }

    def parse_file(
        self,
        file_path: Union[str, Path],
        temporal_context: Optional[PipelineContext] = None,
    ) -> pl.DataFrame:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"檔案不存在: {file_path}")

        encoding = self._detect_encoding(path)
        lines = path.read_text(encoding=encoding, errors="replace").splitlines()
        header_line = self.point_manager.parse_point_definitions(lines=lines, max_lines=500)
        if header_line < 0:
            raise HeaderValidationError("E104: 無法定位 Siemens 資料表頭 (<>,Date)")

        self._file_metadata = self._extract_file_metadata(lines[:header_line], encoding, header_line)

        try:
            df = pl.read_csv(
                path,
                skip_rows=header_line,
                encoding=encoding,
                separator=",",
                null_values=list(set(NULL_VALUES + ["No Data"])),
                infer_schema_length=1000,
                ignore_errors=True,
                truncate_ragged_lines=True,
            )
        except Exception as exc:
            raise DataValidationError(f"無法讀取 Siemens CSV: {exc}") from exc

        if df.width == 0:
            raise DataValidationError("E106: Siemens CSV 解析結果為空")

        rename_map = self.point_manager.get_column_rename_map(df.columns)
        df = df.rename(rename_map)
        df = self._clean_and_cast(df)
        df = self._merge_datetime_columns(df)
        df = self._standardize_timezone(
            df,
            assumed_tz=self.config.get("assumed_timezone", "Asia/Taipei"),
        )
        self.validate_output(df)

        self._inject_pipeline_origin_timestamp(temporal_context=temporal_context)
        self._metadata.update(
            {
                "encoding": encoding,
                "header_line": header_line,
                "row_count": df.height,
                "column_count": df.width,
                "timestamp_range": {
                    "min": str(df["timestamp"].min()) if df.height else None,
                    "max": str(df["timestamp"].max()) if df.height else None,
                },
                "schema": {col: str(dtype) for col, dtype in zip(df.columns, df.dtypes)},
            }
        )

        self._validate_metadata_completeness()
        return df

    def _clean_and_cast(self, df: pl.DataFrame) -> pl.DataFrame:
        for col in df.columns:
            if col in {"Date", "Time", "DateTime", "timestamp"}:
                continue
            if df[col].dtype == pl.Utf8:
                df = df.with_columns(
                    pl.col(col).str.replace_all(r"[^0-9.\-eE]", "").alias(f"{col}_cleaned")
                )
                df = df.with_columns(
                    pl.when(pl.col(f"{col}_cleaned") == "")
                    .then(None)
                    .otherwise(pl.col(f"{col}_cleaned"))
                    .alias(f"{col}_cleaned")
                )
                df = df.with_columns(pl.col(f"{col}_cleaned").cast(pl.Float64, strict=False).alias(col))
                df = df.drop(f"{col}_cleaned")
        return df

    def _merge_datetime_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        if "Date" in df.columns and "Time" in df.columns:
            df = df.with_columns(
                (pl.col("Date") + " " + pl.col("Time"))
                .str.strptime(pl.Datetime, format="%Y/%m/%d %H:%M:%S", strict=False)
                .alias("timestamp")
            )
            return df

        if "DateTime" in df.columns:
            df = df.with_columns(
                pl.col("DateTime").str.strptime(pl.Datetime, format="%Y/%m/%d %H:%M:%S", strict=False).alias("timestamp")
            )
            return df

        raise DataValidationError("E103: Siemens 解析後缺少 Date/Time 或 DateTime 欄位")

    def _extract_file_metadata(self, header_lines: list[str], encoding: str, header_line: int) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "encoding": encoding,
            "header_line": header_line,
            "time_interval": None,
            "date_range": None,
            "report_timings": None,
            "point_count": len(self.point_manager.get_point_metadata()),
        }

        for line in header_lines:
            if line.startswith('"Time Interval:"'):
                metadata["time_interval"] = self._extract_second_csv_cell(line)
            elif line.startswith('"Date Range:"'):
                metadata["date_range"] = self._extract_second_csv_cell(line)
            elif line.startswith('"Report Timings:"'):
                metadata["report_timings"] = self._extract_second_csv_cell(line)

        return metadata

    def _extract_second_csv_cell(self, line: str) -> Optional[str]:
        matched = re.findall(r'"([^"]*)"', line)
        if len(matched) >= 2:
            return matched[1]
        return None

    def _validate_metadata_completeness(self) -> None:
        if not self.point_manager.get_point_metadata():
            raise PointMappingError("E106: 無法建立點位映射（Point_N 定義缺失）")

        if not self._metadata.get("pipeline_origin_timestamp"):
            raise MetadataIncompleteError("E107: 缺少 pipeline_origin_timestamp")

