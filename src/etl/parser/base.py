from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import logging

import polars as pl

from src.context import PipelineContext
from src.etl.config_models import VALID_QUALITY_FLAGS_SET
from src.exceptions import ContractViolationError, EncodingError, TimezoneError


class BaseParser(ABC):
    """Abstract base class for parser strategies."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self._metadata: Dict[str, Any] = {}

    @abstractmethod
    def parse_file(
        self,
        file_path: Union[str, Path],
        temporal_context: Optional[PipelineContext] = None,
    ) -> pl.DataFrame:
        """Parse file and return contract-compliant DataFrame."""

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return parse metadata for diagnostics and downstream modules."""

    def parse_with_metadata(
        self,
        file_path: Union[str, Path],
        temporal_context: Optional[PipelineContext] = None,
    ) -> Tuple[pl.DataFrame, Dict[str, Any]]:
        df = self.parse_file(file_path=file_path, temporal_context=temporal_context)
        return df, self.get_metadata()

    def validate_output(self, df: pl.DataFrame) -> None:
        """Validate output against parser contract (E101-E103)."""
        errors = []

        if "timestamp" not in df.columns:
            errors.append("E103: 缺少必要欄位 'timestamp'")
        else:
            ts_dtype = df["timestamp"].dtype
            if not isinstance(ts_dtype, pl.Datetime):
                errors.append(f"E102: timestamp 必須為 Datetime，得到 {ts_dtype}")
            else:
                if str(ts_dtype.time_zone) != "UTC":
                    errors.append(f"E102: timestamp 時區必須為 UTC，得到 {ts_dtype.time_zone}")
                if ts_dtype.time_unit != "ns":
                    errors.append(f"E102: timestamp 精度必須為 nanoseconds，得到 {ts_dtype.time_unit}")

        for col in df.columns:
            if df[col].dtype == pl.Utf8:
                if df[col].str.contains("\ufeff").any():
                    errors.append(f"E101: 欄位 '{col}' 包含 UTF-8 BOM 殘留")
                if df[col].str.contains("\x00").any():
                    errors.append(f"E101: 欄位 '{col}' 包含 Null byte")

        if "quality_flags" in df.columns:
            invalid = (
                df.explode("quality_flags")
                .filter(pl.col("quality_flags").is_not_null())
                .filter(~pl.col("quality_flags").is_in(list(VALID_QUALITY_FLAGS_SET)))
            )
            if invalid.height > 0:
                errors.append("E103: quality_flags 含未定義值，與 SSOT 不一致")

        if errors:
            raise ContractViolationError(
                f"Parser 輸出契約驗證失敗 ({len(errors)} 項):\n" + "\n".join(errors)
            )

    def _detect_encoding(self, file_path: Path) -> str:
        with open(file_path, "rb") as f:
            raw = f.read(4)
            if raw.startswith(b"\xef\xbb\xbf"):
                return "utf-8-sig"
            if raw.startswith(b"\xff\xfe"):
                return "utf-16-le"
            if raw.startswith(b"\xfe\xff"):
                return "utf-16-be"

        for encoding in ["utf-8", "cp950", "utf-16"]:
            try:
                with open(file_path, "rb") as f:
                    f.read().decode(encoding)
                    return encoding
            except (UnicodeDecodeError, LookupError):
                continue
        raise EncodingError(f"E101: 無法偵測檔案編碼: {file_path}")

    def _standardize_timezone(self, df: pl.DataFrame, assumed_tz: str = "Asia/Taipei") -> pl.DataFrame:
        if "timestamp" not in df.columns:
            raise TimezoneError("E103: 缺少必要欄位 'timestamp'")

        ts_dtype = df["timestamp"].dtype
        if not isinstance(ts_dtype, pl.Datetime):
            raise TimezoneError(f"E102: timestamp 必須為 Datetime，得到 {ts_dtype}")

        if str(ts_dtype.time_zone) == "UTC":
            return df.with_columns(pl.col("timestamp").dt.cast_time_unit("ns"))

        if ts_dtype.time_zone is not None:
            return df.with_columns(
                pl.col("timestamp").dt.convert_time_zone("UTC").dt.cast_time_unit("ns")
            )

        return df.with_columns(
            pl.col("timestamp")
            .dt.replace_time_zone(assumed_tz)
            .dt.convert_time_zone("UTC")
            .dt.cast_time_unit("ns")
        )

    def _inject_pipeline_origin_timestamp(
        self,
        temporal_context: Optional[PipelineContext] = None,
    ) -> str:
        if temporal_context is not None:
            baseline = temporal_context.get_baseline()
        else:
            ctx = PipelineContext()
            if ctx.is_initialized():
                baseline = ctx.get_baseline()
            else:
                baseline = datetime.now(timezone.utc)

        iso = baseline.astimezone(timezone.utc).isoformat()
        self._metadata["pipeline_origin_timestamp"] = iso
        return iso

