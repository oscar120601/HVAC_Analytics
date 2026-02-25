from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union
import re

import yaml


MAX_HEADER_SCAN_LINES = 500

HEADER_KEYWORDS = {
    "timestamp": [
        "Date", "Time", "日期", "時間", "DateTime", "Timestamp", "时间",
        "日期時間", "timestamp", "datetime",
    ],
    "required": ["Date", "日期", "Time", "時間"],
}

NULL_VALUES = [
    "", "NA", "null", "NULL", "---", "Error", "N/A", "OFF", "OFFLINE",
    "#VALUE!", "#N/A", "None", "--", "NaN", "nan", "Null",
]

DEFAULT_SITE_CONFIG: Dict[str, Any] = {
    "parser_type": "generic",
    "encoding": "auto",
    "delimiter": ",",
    "header_keywords": HEADER_KEYWORDS,
    "assumed_timezone": "Asia/Taipei",
    "null_values": NULL_VALUES,
    "column_mapping": {},
    "max_header_scan_lines": MAX_HEADER_SCAN_LINES,
}


def deep_merge_dict(parent: Dict[str, Any], child: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge nested dictionaries, child overrides parent."""
    result = dict(parent)
    for k, v in child.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge_dict(result[k], v)
        else:
            result[k] = v
    return result


def load_site_config(
    site_id: str = "default",
    config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    if config_path is None:
        config_path = Path(__file__).resolve().parents[3] / "config" / "site_templates.yaml"

    config_file = Path(config_path)
    if not config_file.exists():
        return dict(DEFAULT_SITE_CONFIG)

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            all_configs = yaml.safe_load(f) or {}
    except Exception:
        return dict(DEFAULT_SITE_CONFIG)

    if site_id not in all_configs:
        site_id = "default"

    if site_id not in all_configs:
        return dict(DEFAULT_SITE_CONFIG)

    cfg = all_configs[site_id] or {}
    inherit = cfg.get("inherit")
    if inherit:
        parent_cfg = all_configs.get(inherit, {})
        cfg = deep_merge_dict(parent_cfg, cfg)
        cfg.pop("inherit", None)

    return deep_merge_dict(DEFAULT_SITE_CONFIG, cfg)


def normalize_header_name(header: str, mapping: Optional[Dict[str, str]] = None) -> str:
    """Normalize header to snake_case while preserving Date/Time compatibility."""
    mapping = mapping or {}
    mapping_rules = {
        "日期": "Date",
        "時間": "Time",
        "日期時間": "DateTime",
        "Date": "Date",
        "Time": "Time",
        "DateTime": "DateTime",
        "timestamp": "timestamp",
        "<>Date": "Date",
        "<>Time": "Time",
    }

    h = header.strip().replace('"', "").replace("'", "")
    h = re.sub(r"^<>", "", h)
    h = h.replace("<", "").replace(">", "")

    if h in mapping:
        return mapping[h]
    if h in mapping_rules:
        return mapping_rules[h]

    h = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", h)
    h = re.sub(r"[^\w]", "_", h)
    h = re.sub(r"_+", "_", h).strip("_")
    if re.match(r"^[0-9]", h):
        h = f"col_{h}"
    return h.lower()

