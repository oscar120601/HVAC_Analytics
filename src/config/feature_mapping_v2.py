"""
Feature Mapping Configuration System - Enhanced Version.

Supports dynamic feature categories and custom feature groups.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


# Standard feature categories with metadata
STANDARD_CATEGORIES = {
    "load": {
        "name": "負載 (Load)",
        "icon": "🏭",
        "unit": "RT",
        "description": "冷凍機製冷負載",
        "pattern": "RT"
    },
    "chw_pump": {
        "name": "冷凍泵 (CHW Pumps)",
        "icon": "💧",
        "unit": "Hz",
        "description": "冷凍水幫浦頻率",
        "pattern": "CHP"
    },
    "cw_pump": {
        "name": "冷卻泵 (CW Pumps)",
        "icon": "🌊",
        "unit": "Hz",
        "description": "冷卻水幫浦頻率",
        "pattern": "CWP"
    },
    "ct_fan": {
        "name": "冷卻塔 (CT Fans)",
        "icon": "🌀",
        "unit": "Hz",
        "description": "冷卻塔風扇頻率",
        "pattern": "CT_"
    },
    "temperature": {
        "name": "溫度 (Temperatures)",
        "icon": "🌡️",
        "unit": "°C",
        "description": "水系統溫度",
        "pattern": "SWT|RWT|TEMP"
    },
    "environment": {
        "name": "環境 (Environment)",
        "icon": "🌍",
        "unit": "°C/%",
        "description": "外氣溫度/濕度/濕球溫度",
        "pattern": "OAT|OAH|WBT|OUTDOOR|AMB"
    },
    "pressure": {
        "name": "壓力 (Pressure)",
        "icon": "📊",
        "unit": "kPa",
        "description": "水系統壓力",
        "pattern": "PRESSURE|PSI|KPA"
    },
    "flow": {
        "name": "流量 (Flow)",
        "icon": "🌊",
        "unit": "LPM/GPM",
        "description": "水流量",
        "pattern": "FLOW|LPM|GPM"
    },
    "power": {
        "name": "設備耗電 (Device Power)",
        "icon": "⚡",
        "unit": "kW",
        "description": "個別設備耗電量",
        "pattern": "POWER|KW"
    },
    "status": {
        "name": "狀態 (Status)",
        "icon": "🔘",
        "unit": "ON/OFF",
        "description": "設備運轉狀態",
        "pattern": "STATUS|STATE|ON|OFF|RUN"
    }
}


@dataclass
class FeatureMapping:
    """
    Enhanced feature mapping with support for dynamic categories.
    
    Example:
        mapping = FeatureMapping(
            load_cols=["CH_0_RT"],
            chw_pump_hz_cols=["CHP_01_VFD_OUT"],
            target_col="CH_SYS_TOTAL_KW",
            custom_categories={
                "pressure": ["CHW_PRESSURE", "CW_PRESSURE"],
                "flow": ["CHW_FLOW", "CW_FLOW"]
            }
        )
    """
    
    # Standard categories (保留向後兼容)
    load_cols: List[str] = field(default_factory=list)
    chw_pump_hz_cols: List[str] = field(default_factory=list)
    cw_pump_hz_cols: List[str] = field(default_factory=list)
    ct_fan_hz_cols: List[str] = field(default_factory=list)
    temp_cols: List[str] = field(default_factory=list)
    env_cols: List[str] = field(default_factory=list)
    
    # Target variable
    target_col: str = "CH_SYS_TOTAL_KW"
    
    # Dynamic custom categories
    custom_categories: Dict[str, List[str]] = field(default_factory=dict)
    
    # Category metadata (for UI display)
    category_metadata: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize metadata for custom categories."""
        if not self.category_metadata:
            self.category_metadata = {}
        
        # Merge with standard categories
        for cat_id, meta in STANDARD_CATEGORIES.items():
            if cat_id not in self.category_metadata:
                self.category_metadata[cat_id] = meta
    
    def get_all_categories(self) -> Dict[str, List[str]]:
        """Get all feature categories (standard + custom)."""
        categories = {
            "load": self.load_cols,
            "chw_pump": self.chw_pump_hz_cols,
            "cw_pump": self.cw_pump_hz_cols,
            "ct_fan": self.ct_fan_hz_cols,
            "temperature": self.temp_cols,
            "environment": self.env_cols,
        }
        
        # Add custom categories
        categories.update(self.custom_categories)
        
        return categories
    
    def get_all_feature_cols(self) -> List[str]:
        """Get all feature column names (excluding target)."""
        all_cols = []
        for cols in self.get_all_categories().values():
            all_cols.extend(cols)
        return all_cols
    
    def get_category_columns(self, category_id: str) -> List[str]:
        """Get columns for a specific category."""
        if category_id in self.custom_categories:
            return self.custom_categories[category_id]
        
        # Standard categories
        category_map = {
            "load": self.load_cols,
            "chw_pump": self.chw_pump_hz_cols,
            "cw_pump": self.cw_pump_hz_cols,
            "ct_fan": self.ct_fan_hz_cols,
            "temperature": self.temp_cols,
            "environment": self.env_cols,
        }
        
        return category_map.get(category_id, [])
    
    def set_category_columns(self, category_id: str, columns: List[str]):
        """Set columns for a category (creates custom category if not standard)."""
        standard_setters = {
            "load": lambda x: setattr(self, 'load_cols', x),
            "chw_pump": lambda x: setattr(self, 'chw_pump_hz_cols', x),
            "cw_pump": lambda x: setattr(self, 'cw_pump_hz_cols', x),
            "ct_fan": lambda x: setattr(self, 'ct_fan_hz_cols', x),
            "temperature": lambda x: setattr(self, 'temp_cols', x),
            "environment": lambda x: setattr(self, 'env_cols', x),
        }
        
        if category_id in standard_setters:
            standard_setters[category_id](columns)
        else:
            self.custom_categories[category_id] = columns
    
    def add_custom_category(self, category_id: str, columns: List[str], 
                           name: str = None, icon: str = "📦", 
                           unit: str = "", description: str = ""):
        """
        Add a new custom feature category.
        
        Args:
            category_id: Unique identifier (e.g., "pressure", "flow_rate")
            columns: List of column names
            name: Display name
            icon: Emoji icon for UI
            unit: Measurement unit
            description: Description for UI
        """
        self.custom_categories[category_id] = columns
        
        self.category_metadata[category_id] = {
            "name": name or category_id,
            "icon": icon,
            "unit": unit,
            "description": description,
            "pattern": ""
        }
        
        logger.info(f"Added custom category '{category_id}' with {len(columns)} columns")
    
    def remove_custom_category(self, category_id: str):
        """Remove a custom category."""
        if category_id in self.custom_categories:
            del self.custom_categories[category_id]
            if category_id in self.category_metadata:
                del self.category_metadata[category_id]
            logger.info(f"Removed custom category '{category_id}'")
    
    def get_category_info(self, category_id: str) -> Dict[str, str]:
        """Get metadata for a category."""
        if category_id in self.category_metadata:
            return self.category_metadata[category_id]
        
        # Default info for unknown categories
        return {
            "name": category_id,
            "icon": "📦",
            "unit": "",
            "description": "",
            "pattern": ""
        }
    
    def validate_against_dataframe(self, df_columns: List[str]) -> Dict[str, Any]:
        """
        Validate mapping against actual dataframe columns.
        
        Returns:
            Dict with validation results
        """
        all_mapped = self.get_all_feature_cols()
        
        matched = [col for col in all_mapped if col in df_columns]
        missing = [col for col in all_mapped if col not in df_columns]
        
        # Categorize missing columns
        missing_by_category = {}
        for cat_id, cols in self.get_all_categories().items():
            cat_missing = [c for c in cols if c not in df_columns]
            if cat_missing:
                missing_by_category[cat_id] = cat_missing
        
        return {
            "matched": matched,
            "missing": missing,
            "missing_by_category": missing_by_category,
            "available_in_df": [col for col in df_columns if col not in all_mapped],
            "match_rate": len(matched) / len(all_mapped) if all_mapped else 0
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "load_cols": self.load_cols,
            "chw_pump_hz_cols": self.chw_pump_hz_cols,
            "cw_pump_hz_cols": self.cw_pump_hz_cols,
            "ct_fan_hz_cols": self.ct_fan_hz_cols,
            "temp_cols": self.temp_cols,
            "env_cols": self.env_cols,
            "target_col": self.target_col,
            "custom_categories": self.custom_categories,
            "category_metadata": self.category_metadata
        }
    
    def save(self, path: str) -> None:
        """Save mapping to JSON file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"Feature mapping saved to {path}")
    
    @classmethod
    def load(cls, path: str) -> "FeatureMapping":
        """Load mapping from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)
    
    @classmethod
    def create_from_dataframe(
        cls,
        df_columns: List[str],
        auto_patterns: Dict[str, str] = None
    ) -> "FeatureMapping":
        """
        Auto-create mapping from dataframe columns.
        
        Args:
            df_columns: List of column names
            auto_patterns: Optional custom patterns for auto-detection
        """
        # Default patterns
        patterns = {
            "load": ("RT", ["RT"]),
            "chw_pump": ("CHP", ["CHP", "VFD"]),
            "cw_pump": ("CWP", ["CWP", "VFD"]),
            "ct_fan": ("CT_", ["CT_", "VFD"]),
            "temperature": ("TEMP", ["SWT", "RWT", "TEMP"]),
            "environment": ("ENV", ["OAT", "OAH", "WBT", "OUTDOOR", "AMB"]),
            "pressure": ("PRESSURE", ["PRESSURE", "PSI", "KPA", "BAR"]),
            "flow": ("FLOW", ["FLOW", "LPM", "GPM", "L/S"]),
            "power": ("POWER", ["POWER", "KW", "ENERGY"]),
            "status": ("STATUS", ["STATUS", "STATE", "ON", "OFF", "RUN", "ENABLE"])
        }
        
        # Override with custom patterns if provided
        if auto_patterns:
            patterns.update(auto_patterns)
        
        # Auto-detect columns for each category
        category_columns = {}
        
        for cat_id, (name, pattern_list) in patterns.items():
            matched_cols = []
            for col in df_columns:
                col_upper = col.upper()
                # Check if any pattern matches
                if any(p.upper() in col_upper for p in pattern_list):
                    # Exclude certain patterns (e.g., frozen flags)
                    if "FROZEN" not in col_upper and "FLAG" not in col_upper:
                        matched_cols.append(col)
            
            if matched_cols:
                category_columns[cat_id] = sorted(matched_cols)
        
        # Separate standard and custom categories
        standard_cats = ["load", "chw_pump", "cw_pump", "ct_fan", "temperature", "environment"]
        
        mapping = cls(
            load_cols=category_columns.get("load", []),
            chw_pump_hz_cols=category_columns.get("chw_pump", []),
            cw_pump_hz_cols=category_columns.get("cw_pump", []),
            ct_fan_hz_cols=category_columns.get("ct_fan", []),
            temp_cols=category_columns.get("temperature", []),
            env_cols=category_columns.get("environment", []),
            custom_categories={k: v for k, v in category_columns.items() if k not in standard_cats}
        )
        
        # Auto-detect target
        target_candidates = [c for c in df_columns if "TOTAL" in c.upper() and "KW" in c.upper()]
        if not target_candidates:
            target_candidates = [c for c in df_columns if c.upper().endswith("_KW")]
        if target_candidates:
            mapping.target_col = target_candidates[0]
        
        logger.info(f"Auto-created mapping with {len(mapping.get_all_feature_cols())} features")
        return mapping


# Predefined mappings
PREDEFINED_MAPPINGS = {
    "default": FeatureMapping.create_from_dataframe([
        "CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT",
        "CHP_01_VFD_OUT", "CHP_02_VFD_OUT",
        "CWP_01_VFD_OUT", "CWP_02_VFD_OUT",
        "CT_01_VFD_OUT", "CT_02_VFD_OUT",
        "CH_0_SWT", "CH_0_RWT",
        "CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT",
        "CH_SYS_TOTAL_KW"
    ])
}


def get_feature_mapping(name_or_path: str = "default") -> FeatureMapping:
    """Get feature mapping by name or load from file."""
    if name_or_path in PREDEFINED_MAPPINGS:
        return PREDEFINED_MAPPINGS[name_or_path]
    
    path = Path(name_or_path)
    if path.exists() and path.suffix == '.json':
        return FeatureMapping.load(name_or_path)
    
    logger.warning(f"Unknown mapping '{name_or_path}', using default")
    return PREDEFINED_MAPPINGS["default"]


if __name__ == "__main__":
    # Example: Create mapping with custom categories
    
    # Example 1: Standard usage
    print("=== Example 1: Standard Categories ===")
    mapping = FeatureMapping.create_from_dataframe([
        "CH_0_RT", "CHP_01_VFD_OUT", "CWP_01_VFD_OUT",
        "CT_01_VFD_OUT", "CH_0_SWT", "CT_SYS_OAT",
        "CH_SYS_TOTAL_KW"
    ])
    print(f"Categories: {list(mapping.get_all_categories().keys())}")
    
    # Example 2: Add custom category
    print("\n=== Example 2: With Custom Categories ===")
    mapping.add_custom_category(
        category_id="pressure",
        columns=["CHW_PRESSURE", "CW_PRESSURE"],
        name="壓力 (Pressure)",
        icon="📊",
        unit="kPa",
        description="水系統壓力監測"
    )
    
    mapping.add_custom_category(
        category_id="flow",
        columns=["CHW_FLOW", "CW_FLOW"],
        name="流量 (Flow)",
        icon="🌊",
        unit="LPM",
        description="水流量監測"
    )
    
    print(f"All categories: {list(mapping.get_all_categories().keys())}")
    print(f"Total features: {len(mapping.get_all_feature_cols())}")
    
    # Example 3: Display category info
    print("\n=== Category Information ===")
    for cat_id in mapping.get_all_categories().keys():
        info = mapping.get_category_info(cat_id)
        print(f"{info['icon']} {info['name']} ({info['unit']})")
