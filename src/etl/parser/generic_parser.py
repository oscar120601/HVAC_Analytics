from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import re

import polars as pl

from src.exceptions import DataValidationError, HeaderValidationError
from src.context import PipelineContext

from .base import BaseParser
from .utils import (
    DEFAULT_SITE_CONFIG,
    HEADER_KEYWORDS,
    MAX_HEADER_SCAN_LINES,
    NULL_VALUES,
    deep_merge_dict,
    normalize_header_name,
)


class GenericParser(BaseParser):
    """
    Generic CSV parser with v2.1-compatible behavior.

    Supported formats:
    - Date + Time columns
    - DateTime column
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        merged = deep_merge_dict(DEFAULT_SITE_CONFIG, config or {})
        super().__init__(merged)

    def get_metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)

    def parse_file(
        self,
        file_path: Union[str, Path],
        temporal_context: Optional[PipelineContext] = None,
    ) -> pl.DataFrame:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"檔案不存在: {file_path}")

        encoding = self._detect_encoding(path)
        header_line = self._find_header_line(path, encoding)

        try:
            with open(path, "r", encoding=encoding, errors="replace") as f:
                header_raw = ""
                for idx, line in enumerate(f):
                    if idx == header_line:
                        header_raw = line
                        break
            delimiter = self._detect_delimiter(header_raw)

            df = pl.read_csv(
                path,
                skip_rows=header_line,
                encoding=encoding,
                separator=delimiter,
                null_values=self.config.get("null_values", NULL_VALUES),
                infer_schema_length=1000,
                ignore_errors=True,
                truncate_ragged_lines=True,
            )
        except Exception as exc:
            raise DataValidationError(f"無法讀取 CSV 資料: {exc}") from exc

        normalized_headers = self._normalize_header(df.columns)
        df = df.rename(dict(zip(df.columns, normalized_headers)))
        df = self._clean_and_cast(df)
        df = self._standardize_timezone(
            df,
            assumed_tz=self.config.get("assumed_timezone", "Asia/Taipei"),
        )
        self.validate_output(df)

        self._inject_pipeline_origin_timestamp(temporal_context=temporal_context)
        self._metadata.update(
            {
                "parser_type": "generic",
                "encoding": encoding,
                "header_line": header_line,
                "delimiter": delimiter,
                "row_count": df.height,
                "column_count": df.width,
                "timestamp_range": {
                    "min": str(df["timestamp"].min()) if df.height else None,
                    "max": str(df["timestamp"].max()) if df.height else None,
                },
                "schema": {col: str(dtype) for col, dtype in zip(df.columns, df.dtypes)},
            }
        )
        return df

    def _count_delimiters(self, line: str) -> Dict[str, int]:
        return {
            ",": line.count(","),
            "\t": line.count("\t"),
            ";": line.count(";"),
        }

    def _detect_delimiter(self, line: str) -> str:
        counts = self._count_delimiters(line or "")
        main_delim = max(counts, key=counts.get)
        if counts[main_delim] == 0:
            return self.config.get("delimiter", ",")
        return main_delim

    def _find_header_line(self, file_path: Path, encoding: str) -> int:
        header_keywords = self.config.get("header_keywords", HEADER_KEYWORDS)
        max_scan_lines = self.config.get("max_header_scan_lines", MAX_HEADER_SCAN_LINES)
        required_keywords = set(header_keywords.get("required", HEADER_KEYWORDS["required"]))

        try:
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_scan_lines:
                        break
                    lines.append(line.rstrip("\n\r"))
        except Exception as exc:
            raise HeaderValidationError(f"無法讀取檔案: {file_path}, 錯誤: {exc}") from exc

        candidates = []
        for i, line in enumerate(lines):
            score = 0
            line_upper = line.upper()
            has_date = any(kw.upper() in line_upper for kw in ["DATE", "日期"])
            has_time = any(kw.upper() in line_upper for kw in ["TIME", "時間"])
            has_datetime = any(kw.upper() in line_upper for kw in ["DATETIME", "TIMESTAMP", "日期時間"])
            if has_date and has_time:
                score += 2
            if has_datetime:
                score += 2

            has_required = any(kw.upper() in line_upper for kw in required_keywords)
            if not has_required:
                continue

            delims = self._count_delimiters(line)
            total_delims = sum(delims.values())
            if total_delims > 3:
                score += 1
            if total_delims > 10:
                score += 1

            if i + 1 < len(lines):
                next_delims = self._count_delimiters(lines[i + 1])
                main_delim = max(delims, key=delims.get)
                if abs(delims[main_delim] - next_delims.get(main_delim, 0)) <= 1:
                    score += 1

            candidates.append((i, score))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_line, best_score = candidates[0]
            if best_score >= 2:
                return best_line

        raise HeaderValidationError(
            f"E104: 無法定位標頭行，已掃描 {len(lines)} 行。"
        )

    def _normalize_header(self, headers: List[str]) -> List[str]:
        column_mapping = self.config.get("column_mapping", {})
        normalized = [normalize_header_name(h, column_mapping) for h in headers]
        duplicates = self._find_duplicates(normalized)
        if duplicates:
            dup_str = ", ".join(sorted(duplicates))
            raise DataValidationError(f"E105: 標頭正規化後存在重複欄位名稱: {dup_str}")
        return normalized

    def _find_duplicates(self, values: List[str]) -> set[str]:
        seen = set()
        duplicates = set()
        for value in values:
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        return duplicates

    def _clean_and_cast(self, df: pl.DataFrame) -> pl.DataFrame:
        null_values = self.config.get("null_values", NULL_VALUES)
        for col in df.columns:
            if col in ["Date", "Time", "timestamp", "DateTime"]:
                continue
            if df[col].dtype == pl.Utf8:
                for null_val in null_values:
                    df = df.with_columns(
                        pl.when(pl.col(col) == null_val).then(None).otherwise(pl.col(col)).alias(col)
                    )
                df = df.with_columns(
                    pl.col(col).str.replace_all(r"[^0-9.\-eE]", "").alias(f"{col}_cleaned")
                )
                df = df.with_columns(
                    pl.when(pl.col(f"{col}_cleaned") == "")
                    .then(None)
                    .otherwise(pl.col(f"{col}_cleaned"))
                    .alias(f"{col}_cleaned")
                )
                df = df.with_columns(
                    pl.col(f"{col}_cleaned").cast(pl.Float64, strict=False).alias(col)
                ).drop(f"{col}_cleaned")

        return self._merge_datetime_columns(df)

    def _merge_datetime_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        if "Date" in df.columns and "Time" in df.columns:
            if df["Date"].dtype == pl.Utf8:
                df = df.with_columns(
                    (pl.col("Date") + " " + pl.col("Time"))
                    .str.strptime(pl.Datetime, format="%Y/%m/%d %H:%M:%S", strict=False)
                    .alias("timestamp")
                )
            else:
                df = df.with_columns(pl.col("Date").dt.combine(pl.col("Time")).alias("timestamp"))
        elif "DateTime" in df.columns:
            if df["DateTime"].dtype == pl.Utf8:
                df = df.with_columns(
                    pl.col("DateTime")
                    .str.strptime(pl.Datetime, format="%Y/%m/%d %H:%M:%S", strict=False)
                    .alias("timestamp")
                )
            else:
                df = df.with_columns(pl.col("DateTime").cast(pl.Datetime).alias("timestamp"))

        if "timestamp" not in df.columns:
            raise DataValidationError(
                "E103: 無法建立 timestamp 欄位。請確認輸入檔案包含 Date + Time 或 DateTime 欄位。"
            )
        return df

