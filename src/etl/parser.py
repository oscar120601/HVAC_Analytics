"""
Compatibility shim for parser imports.

Notes:
- New implementation lives in `src/etl/parser/` package (v2.2 Strategy Pattern).
- This module is intentionally thin and re-exports the v2.2 API so direct file-path
  imports or legacy references still resolve to the same objects.
"""

from src.etl.parser import (  # noqa: F401
    BaseParser,
    GenericParser,
    LegacyReportParser,
    ParserFactory,
    ReportParser,
    SiemensSchedulerReportParser,
    get_parser,
)

__all__ = [
    "BaseParser",
    "GenericParser",
    "SiemensSchedulerReportParser",
    "ParserFactory",
    "get_parser",
    "ReportParser",
    "LegacyReportParser",
]

