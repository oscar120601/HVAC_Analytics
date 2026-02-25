from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import csv
import re


@dataclass
class PointDefinition:
    """Siemens point definition row."""

    point_id: str
    name: str
    suffix: str
    interval: str
    override_name: Optional[str] = None

    @property
    def normalized_name(self) -> str:
        target = self.override_name or self.name
        name = target.replace("-", "_").replace(".", "_")
        name = re.sub(r"[^\w]", "_", name)
        name = re.sub(r"_+", "_", name).strip("_")
        return name.lower()


class PointMappingManager:
    """Map Point_N columns to normalized equipment names."""

    def __init__(self, overrides: Optional[Dict[str, str]] = None):
        self._mapping: Dict[str, PointDefinition] = {}
        self._header_line: int = -1
        self._overrides = overrides or {}

    def parse_point_definitions(self, lines: List[str], max_lines: int = 500) -> int:
        for i, line in enumerate(lines[:max_lines]):
            parsed = self._parse_csv_line(line)
            if not parsed:
                continue

            # Data header line marker
            if parsed and parsed[0].strip() == "<>Date":
                self._header_line = i
                break

            # Point definition row: Point_N:
            head = parsed[0].strip()
            match = re.match(r"^Point_(\d+):$", head)
            if not match:
                continue

            point_num = match.group(1)
            point_id = f"Point_{point_num}"
            name = parsed[1].strip() if len(parsed) > 1 else point_id
            suffix = parsed[2].strip() if len(parsed) > 2 else ""
            interval = parsed[3].strip() if len(parsed) > 3 else ""
            self._mapping[point_id] = PointDefinition(
                point_id=point_id,
                name=name,
                suffix=suffix,
                interval=interval,
                override_name=self._overrides.get(point_id),
            )

        return self._header_line

    def get_column_rename_map(self, csv_headers: List[str]) -> Dict[str, str]:
        rename_map: Dict[str, str] = {}
        used_names: Dict[str, int] = {}

        for header in csv_headers:
            if header in {"Date", "Time", "timestamp", "DateTime", "<>Date"}:
                if header == "<>Date":
                    rename_map[header] = "Date"
                else:
                    rename_map[header] = header
                continue

            if header.startswith("Point_") and header in self._mapping:
                candidate = self._mapping[header].normalized_name
            else:
                candidate = self._normalize_generic(header)

            count = used_names.get(candidate, 0)
            if count:
                renamed = f"{candidate}_{count + 1}"
            else:
                renamed = candidate
            used_names[candidate] = count + 1
            rename_map[header] = renamed

        return rename_map

    def get_point_metadata(self) -> Dict[str, Dict]:
        return {
            point_id: {
                "name": definition.name,
                "suffix": definition.suffix,
                "interval": definition.interval,
                "normalized_name": definition.normalized_name,
                "override_name": definition.override_name,
            }
            for point_id, definition in self._mapping.items()
        }

    @property
    def header_line(self) -> int:
        return self._header_line

    def _normalize_generic(self, header: str) -> str:
        h = header.strip().replace('"', "")
        h = re.sub(r"[^\w]", "_", h)
        h = re.sub(r"_+", "_", h).strip("_")
        return h.lower()

    def _parse_csv_line(self, line: str) -> List[str]:
        try:
            row = next(csv.reader([line]))
            return [cell.replace("\ufeff", "").strip() for cell in row]
        except Exception:
            return []

