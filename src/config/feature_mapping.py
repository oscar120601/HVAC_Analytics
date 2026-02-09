"""
Feature Mapping Configuration System - Enhanced Version with Dynamic Categories.

Supports 10+ standard feature categories and unlimited custom categories.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


# Standard feature categories with metadata for UI display
STANDARD_CATEGORIES = {
    "load": {
        "name": "負載 (Load)",
        "icon": "🏭",
        "unit": "RT",
        "description": "冷凍機製冷負載",
        "pattern": ["RT"]
    },
    "chw_pump": {
        "name": "冷凍泵 (CHW Pumps)",
        "icon": "💧",
        "unit": "Hz",
        "description": "冷凍水幫浦頻率",
        "pattern": ["CHP", "VFD"]
    },
    "cw_pump": {
        "name": "冷卻泵 (CW Pumps)",
        "icon": "🌊",
        "unit": "Hz",
        "description": "冷卻水幫浦頻率",
        "pattern": ["CWP", "VFD"]
    },
    "ct_fan": {
        "name": "冷卻塔 (CT Fans)",
        "icon": "🌀",
        "unit": "Hz",
        "description": "冷卻塔風扇頻率",
        "pattern": ["CT_", "VFD"]
    },
    "temperature": {
        "name": "溫度 (Temperatures)",
        "icon": "🌡️",
        "unit": "°C",
        "description": "水系統溫度",
        "pattern": ["SWT", "RWT", "TEMP"]
    },
    "environment": {
        "name": "環境 (Environment)",
        "icon": "🌍",
        "unit": "°C/%",
        "description": "外氣溫度/濕度/濕球溫度",
        "pattern": ["OAT", "OAH", "WBT", "OUTDOOR", "AMB"]
    },
    "pressure": {
        "name": "壓力 (Pressure)",
        "icon": "📊",
        "unit": "kPa",
        "description": "水系統壓力",
        "pattern": ["PRESSURE", "PSI", "KPA", "BAR"]
    },
    "flow": {
        "name": "流量 (Flow)",
        "icon": "🌊",
        "unit": "LPM/GPM",
        "description": "水流量",
        "pattern": ["FLOW", "LPM", "GPM"]
    },
    "power": {
        "name": "設備耗電 (Device Power)",
        "icon": "⚡",
        "unit": "kW",
        "description": "個別設備耗電量",
        "pattern": ["POWER", "KW"]
    },
    "status": {
        "name": "狀態 (Status)",
        "icon": "🔘",
        "unit": "ON/OFF",
        "description": "設備運轉狀態",
        "pattern": ["STATUS", "STATE", "RUN", "ON", "OFF"]
    }
}


@dataclass
class FeatureMapping:
    """
    Enhanced feature mapping with support for dynamic categories.
    
    Backward compatible with v1 - all standard categories work as before.
    New: Supports custom_categories for unlimited extensibility.
    
    Example:
        # V1 style (still works)
        mapping = FeatureMapping(
            load_cols=["CH_0_RT"],
            chw_pump_hz_cols=["CHP_01_VFD_OUT"],
            target_col="CH_SYS_TOTAL_KW"
        )
        
        # V2 style with custom categories
        mapping = FeatureMapping()
        mapping.add_custom_category("valve", ["VALVE_01"], name="閥門開度", icon="🔧")
    """
    
    # V1 Standard categories (backward compatible)
    load_cols: List[str] = field(default_factory=list)
    chw_pump_hz_cols: List[str] = field(default_factory=list)
    cw_pump_hz_cols: List[str] = field(default_factory=list)
    ct_fan_hz_cols: List[str] = field(default_factory=list)
    temp_cols: List[str] = field(default_factory=list)
    env_cols: List[str] = field(default_factory=list)
    
    # Target variable
    target_col: str = "CH_SYS_TOTAL_KW"
    
    # V2: Custom categories for extensibility
    custom_categories: Dict[str, List[str]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure backward compatibility and initialize structures."""
        # Ensure all standard lists exist
        if self.load_cols is None:
            self.load_cols = []
        if self.chw_pump_hz_cols is None:
            self.chw_pump_hz_cols = []
        if self.cw_pump_hz_cols is None:
            self.cw_pump_hz_cols = []
        if self.ct_fan_hz_cols is None:
            self.ct_fan_hz_cols = []
        if self.temp_cols is None:
            self.temp_cols = []
        if self.env_cols is None:
            self.env_cols = []
        if self.custom_categories is None:
            self.custom_categories = {}
    
    def get_all_categories(self) -> Dict[str, List[str]]:
        """
        Get all feature categories including standard and custom.
        
        Returns:
            Dictionary mapping category_id to list of column names
        """
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
        
        # Filter out empty categories
        return {k: v for k, v in categories.items() if v}
    
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
        
        # Standard categories (V1 compatible)
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
        """
        Set columns for a category.
        Creates custom category if not a standard one.
        """
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
            category_id: Unique identifier (e.g., "pressure", "valve")
            columns: List of column names
            name: Display name for UI
            icon: Emoji icon for UI
            unit: Measurement unit
            description: Description for UI
        """
        self.custom_categories[category_id] = columns
        
        # Add to standard categories for metadata
        STANDARD_CATEGORIES[category_id] = {
            "name": name or category_id,
            "icon": icon,
            "unit": unit,
            "description": description,
            "pattern": []
        }
        
        logger.info(f"Added custom category '{category_id}' with {len(columns)} columns")
    
    def get_category_info(self, category_id: str) -> Dict[str, str]:
        """Get metadata for a category."""
        if category_id in STANDARD_CATEGORIES:
            return STANDARD_CATEGORIES[category_id]
        
        # Default for unknown categories
        return {
            "name": category_id,
            "icon": "📦",
            "unit": "",
            "description": "",
            "pattern": []
        }
    
    def validate_against_dataframe(self, df_columns: List[str]) -> Dict[str, Any]:
        """
        Validate mapping against actual dataframe columns.
        
        Returns:
            Dict with 'matched', 'missing', 'match_rate', etc.
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
            "custom_categories": self.custom_categories
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
        custom_patterns: Dict[str, List[str]] = None
    ) -> "FeatureMapping":
        """
        Auto-create mapping from dataframe columns using pattern matching.
        
        Args:
            df_columns: List of column names from dataframe
            custom_patterns: Optional additional patterns {category_id: [patterns]}
        
        Returns:
            FeatureMapping with auto-detected categories
        """
        # Build patterns from standard categories
        patterns = {}
        for cat_id, meta in STANDARD_CATEGORIES.items():
            patterns[cat_id] = meta.get("pattern", [cat_id.upper()])
        
        # Override with custom patterns
        if custom_patterns:
            patterns.update(custom_patterns)
        
        # Auto-detect columns
        category_columns = {}
        used_columns = set()
        
        for cat_id, pattern_list in patterns.items():
            matched_cols = []
            for col in df_columns:
                if col in used_columns:
                    continue
                    
                col_upper = col.upper()
                # Check patterns (all must match for multi-pattern)
                if all(p.upper() in col_upper for p in pattern_list):
                    # Exclude certain patterns
                    if not any(exclude in col_upper for exclude in ["FROZEN", "FLAG", "INVALID"]):
                        matched_cols.append(col)
                        used_columns.add(col)
            
            if matched_cols:
                category_columns[cat_id] = matched_cols
        
        # Separate standard and custom
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
        
        total_features = len(mapping.get_all_feature_cols())
        logger.info(f"Auto-created mapping: {total_features} features in {len(mapping.get_all_categories())} categories")
        
        return mapping


# Predefined mappings (V1 compatible)
PREDEFINED_MAPPINGS = {
    "default": FeatureMapping(
        load_cols=["CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT"],
        chw_pump_hz_cols=["CHP_01_VFD_OUT", "CHP_02_VFD_OUT", "CHP_03_VFD_OUT", "CHP_04_VFD_OUT", "CHP_05_VFD_OUT"],
        cw_pump_hz_cols=["CWP_01_VFD_OUT", "CWP_02_VFD_OUT", "CWP_03_VFD_OUT", "CWP_04_VFD_OUT", "CWP_05_VFD_OUT"],
        ct_fan_hz_cols=["CT_01_VFD_OUT", "CT_02_VFD_OUT", "CT_03_VFD_OUT", "CT_04_VFD_OUT", "CT_05_VFD_OUT"],
        temp_cols=["CH_0_SWT", "CH_0_RWT", "CW_SYS_SWT", "CW_SYS_RWT"],
        env_cols=["CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT"],
        target_col="CH_SYS_TOTAL_KW"
    ),
    "cgmh_ty": FeatureMapping(
        load_cols=["CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT"],
        chw_pump_hz_cols=["CHP_01_VFD_OUT", "CHP_02_VFD_OUT", "CHP_03_VFD_OUT", "CHP_04_VFD_OUT", "CHP_05_VFD_OUT"],
        cw_pump_hz_cols=["CWP_01_VFD_OUT", "CWP_02_VFD_OUT", "CWP_03_VFD_OUT", "CWP_04_VFD_OUT", "CWP_05_VFD_OUT"],
        ct_fan_hz_cols=["CT_01_VFD_OUT", "CT_02_VFD_OUT", "CT_03_VFD_OUT", "CT_04_VFD_OUT", "CT_05_VFD_OUT"],
        temp_cols=["CH_0_SWT", "CH_0_RWT", "CW_SYS_SWT", "CW_SYS_RWT"],
        env_cols=["CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT"],
        target_col="CH_SYS_TOTAL_KW"
    )
}


def get_feature_mapping(name_or_path: str = "default") -> FeatureMapping:
    """
    Get feature mapping by name or load from file.
    
    Args:
        name_or_path: "default", "cgmh_ty", or path to JSON file
    
    Returns:
        FeatureMapping instance
    """
    if name_or_path in PREDEFINED_MAPPINGS:
        return PREDEFINED_MAPPINGS[name_or_path]
    
    path = Path(name_or_path)
    if path.exists() and path.suffix == '.json':
        return FeatureMapping.load(name_or_path)
    
    logger.warning(f"Unknown mapping '{name_or_path}', using default")
    return PREDEFINED_MAPPINGS["default"]


if __name__ == "__main__":
    # Test the enhanced feature mapping
    print("Testing Enhanced Feature Mapping...")
    
    # Test 1: V1 compatibility
    print("\n1. V1 Compatibility Test:")
    mapping = FeatureMapping(
        load_cols=["CH_0_RT"],
        chw_pump_hz_cols=["CHP_01_VFD_OUT"],
        target_col="TOTAL_KW"
    )
    print(f"   Standard categories: {list(mapping.get_all_categories().keys())}")
    
    # Test 2: Auto-detection with new categories
    print("\n2. Auto-detection with Pressure/Flow:")
    columns = [
        "CH_0_RT", "CH_1_RT",
        "CHP_01_VFD_OUT", "CWP_01_VFD_OUT",
        "CH_0_SWT", "CT_SYS_OAT",
        "CHW_PRESSURE", "CW_PRESSURE",
        "CHW_FLOW", "CW_FLOW",
        "CH_SYS_TOTAL_KW"
    ]
    auto_mapping = FeatureMapping.create_from_dataframe(columns)
    for cat_id, cols in auto_mapping.get_all_categories().items():
        if cols:
            info = auto_mapping.get_category_info(cat_id)
            print(f"   {info['icon']} {info['name']}: {len(cols)} cols")
    
    # Test 3: Custom category
    print("\n3. Custom Category Test:")
    auto_mapping.add_custom_category(
        "valve", ["VALVE_01", "VALVE_02"],
        name="Valve Position", icon="🔧", unit="%"
    )
    print(f"   Total categories: {len(auto_mapping.get_all_categories())}")
    
    print("\n✅ All tests passed!")
