"""
Parser v2.2 modular package.

This package provides:
- BaseParser abstraction
- GenericParser (v2.1-compatible behavior)
- SiemensSchedulerReportParser
- ParserFactory and auto-detect
- ReportParser compatibility facade
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import polars as pl

from .base import BaseParser
from .generic_parser import GenericParser
from .siemens.scheduler_report import SiemensSchedulerReportParser
from .utils import load_site_config

logger = logging.getLogger(__name__)


PARSER_STRATEGIES = {
    "generic": GenericParser,
    "siemens_scheduler": SiemensSchedulerReportParser,
}


class ParserFactory:
    """Factory for creating parser strategy instances."""

    _strategies = dict(PARSER_STRATEGIES)

    @classmethod
    def create_parser(
        cls,
        parser_type: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> BaseParser:
        parser_key = (parser_type or "generic").strip().lower()
        parser_cls = cls._strategies.get(parser_key)
        if parser_cls is None:
            available = ", ".join(cls.list_strategies())
            raise ValueError(f"未知 parser_type: {parser_type}. 可用類型: {available}")
        return parser_cls(config=config or {})

    @classmethod
    def register_strategy(cls, name: str, parser_class: type[BaseParser]) -> None:
        if not issubclass(parser_class, BaseParser):
            raise TypeError(f"Parser 類別必須繼承 BaseParser: {parser_class}")
        key = name.strip().lower()
        cls._strategies[key] = parser_class
        logger.info("已註冊 parser strategy: %s -> %s", key, parser_class.__name__)

    @classmethod
    def list_strategies(cls) -> list[str]:
        return sorted(cls._strategies.keys())

    @classmethod
    def auto_detect(
        cls,
        file_path: Union[str, Path],
        config: Optional[Dict[str, Any]] = None,
    ) -> BaseParser:
        path = Path(file_path)
        try:
            sample = path.read_text(encoding="utf-8", errors="ignore")[:6000]
            if '"Point_1:"' in sample and '"<>Date"' in sample:
                logger.info("自動偵測: Siemens Scheduler 格式")
                return cls.create_parser("siemens_scheduler", config)
        except Exception as exc:
            logger.warning("自動偵測失敗，fallback generic: %s", exc)
        logger.info("自動偵測: 使用 generic")
        return cls.create_parser("generic", config)


def get_parser(
    parser_type: str = "generic",
    file_path: Optional[Union[str, Path]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> BaseParser:
    """Convenience helper to get parser instance."""
    if parser_type == "auto":
        if file_path is None:
            raise ValueError("parser_type='auto' 時必須提供 file_path")
        return ParserFactory.auto_detect(file_path=file_path, config=config)
    return ParserFactory.create_parser(parser_type=parser_type, config=config)


class ReportParser:
    """
    Backward-compatible facade for v2.1 callers.

    Old API remains:
    - ReportParser(site_id=..., config_path=...)
    - parse_file()
    - parse_with_metadata()
    - compatibility attributes: header_line / detected_encoding / point_map
    """

    def __init__(
        self,
        site_id: str = "default",
        config_path: Optional[Union[str, Path]] = None,
        annotation_manager: Any = None,  # kept for compatibility, intentionally unused
        parser_type: Optional[str] = None,
    ):
        self.site_id = site_id
        self.logger = logging.getLogger(f"parser.{site_id}")
        self.config = load_site_config(site_id=site_id, config_path=config_path)
        if parser_type:
            self.config["parser_type"] = parser_type
        self.parser_type = self.config.get("parser_type", "generic")
        self._delegate = ParserFactory.create_parser(self.parser_type, self.config)

        # v2.1 compatibility attributes
        self.header_line: int = 0
        self.point_map: Dict[str, str] = {}
        self.detected_encoding: Optional[str] = None

    def parse_file(self, file_path: Union[str, Path], temporal_context: Any = None) -> pl.DataFrame:
        # v2.1 相容：允許呼叫端動態修改 parser.config
        self._delegate.config = self.config
        df = self._delegate.parse_file(file_path=file_path, temporal_context=temporal_context)
        self._sync_compat_state()
        return df

    def parse_with_metadata(
        self,
        file_path: Union[str, Path],
        temporal_context: Any = None,
    ) -> Tuple[pl.DataFrame, Dict[str, Any]]:
        # v2.1 相容：允許呼叫端動態修改 parser.config
        self._delegate.config = self.config
        df, metadata = self._delegate.parse_with_metadata(file_path=file_path, temporal_context=temporal_context)
        self._sync_compat_state(metadata)
        merged = {
            "site_id": self.site_id,
            "detected_encoding": metadata.get("encoding"),
            "header_line": metadata.get("header_line"),
            "row_count": metadata.get("row_count"),
            "column_count": metadata.get("column_count"),
            "timestamp_range": metadata.get("timestamp_range", {}),
            "schema": metadata.get("schema", {}),
            "pipeline_origin_timestamp": metadata.get("pipeline_origin_timestamp"),
            "parser_type": self.parser_type,
            "point_mapping": metadata.get("point_mapping", {}),
        }
        return df, merged

    def parse_metadata(self, file_path: Union[str, Path]) -> Dict[str, str]:
        _, metadata = self.parse_with_metadata(file_path=file_path)
        point_mapping = metadata.get("point_mapping", {})
        return {k: v.get("name", "") for k, v in point_mapping.items()}

    def get_metadata(self) -> Dict[str, Any]:
        metadata = self._delegate.get_metadata()
        return {
            **metadata,
            "site_id": self.site_id,
            "parser_type": self.parser_type,
        }

    # Compatibility passthroughs for v2.1 tests
    def _detect_encoding(self, file_path: Union[str, Path]) -> str:
        return self._delegate._detect_encoding(Path(file_path))

    def _find_header_line(self, file_path: Union[str, Path], encoding: str) -> int:
        finder = getattr(self._delegate, "_find_header_line", None)
        if finder is None:
            raise AttributeError("目前 parser strategy 不支援 _find_header_line")
        return finder(Path(file_path), encoding)

    def _normalize_header(self, headers: list[str]) -> list[str]:
        normalizer = getattr(self._delegate, "_normalize_header", None)
        if normalizer is None:
            raise AttributeError("目前 parser strategy 不支援 _normalize_header")
        return normalizer(headers)

    def _standardize_timezone(self, df: pl.DataFrame) -> pl.DataFrame:
        return self._delegate._standardize_timezone(df, assumed_tz=self.config.get("assumed_timezone", "Asia/Taipei"))

    def _validate_output_contract(self, df: pl.DataFrame) -> None:
        self._delegate.validate_output(df)

    def _sync_compat_state(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        data = metadata or self._delegate.get_metadata()
        self.header_line = int(data.get("header_line", 0) or 0)
        self.detected_encoding = data.get("encoding")
        point_mapping = data.get("point_mapping", {})
        self.point_map = {k: v.get("normalized_name", k.lower()) for k, v in point_mapping.items()}


class LegacyReportParser(ReportParser):
    """Deprecated alias for backward compatibility."""

    def __init__(self):
        super().__init__(site_id="default")
        logger.warning("LegacyReportParser 已棄用，請改用 ReportParser。")


__all__ = [
    "BaseParser",
    "GenericParser",
    "SiemensSchedulerReportParser",
    "ParserFactory",
    "get_parser",
    "ReportParser",
    "LegacyReportParser",
]
