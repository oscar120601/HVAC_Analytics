"""
Feature Mapping Configuration System - Enhanced Version.

Supports dynamic feature categories and custom feature groups.
"""

import json
import logging
import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


# Standard feature categories with metadata
# Organized by HVAC physical system hierarchy
STANDARD_CATEGORIES = {
    # === 冰水側系統 (Chilled Water Side) ===
    "chiller": {
        "name": "冰水機 (Chiller)",
        "icon": "❄️",
        "unit": "RT/kW/°C/LPM",
        "description": "冰水機本體參數：負載、溫度、流量、功率",
        "pattern": "CH_*,CHILLER*",
        "parent_system": "chilled_water_side"
    },
    "chw_pump": {
        "name": "冰水泵 (CHW Pump)",
        "icon": "💧",
        "unit": "Hz/kW/kWh",
        "description": "一次冰水泵：頻率、功率、用電量、狀態",
        "pattern": "CHP*",
        "parent_system": "chilled_water_side"
    },
    "scp_pump": {
        "name": "區域泵 (SCP)",
        "icon": "🔄",
        "unit": "Hz/kW/kWh",
        "description": "二次側區域泵：頻率、功率、用電量、狀態",
        "pattern": "SCP*",
        "parent_system": "chilled_water_side"
    },
    "chw_temp": {
        "name": "冰水溫度 (CHW Temp)",
        "icon": "🌡️",
        "unit": "°C",
        "description": "冰水側系統溫度：供水/回水/溫差",
        "pattern": "*CHW*TEMP*,*CHW*ST*,*CHW*RT*",
        "parent_system": "chilled_water_side"
    },
    "chw_pressure": {
        "name": "冰水壓力 (CHW Pressure)",
        "icon": "📊",
        "unit": "kPa",
        "description": "冰水側系統壓力：供水/回水/壓差",
        "pattern": "*CHW*PRESSURE*,*CHW*P*",
        "parent_system": "chilled_water_side"
    },
    "chw_flow": {
        "name": "冰水流量 (CHW Flow)",
        "icon": "🌊",
        "unit": "LPM",
        "description": "冰水側系統總流量",
        "pattern": "*CHW*FLOW*,*CHW*LPM*",
        "parent_system": "chilled_water_side"
    },
    
    # === 冷卻水側系統 (Condenser Water Side) ===
    "cw_pump": {
        "name": "冷卻水泵 (CW Pump)",
        "icon": "🔥",
        "unit": "Hz/kW/kWh",
        "description": "冷卻水泵：頻率、功率、用電量、狀態",
        "pattern": "CWP*",
        "parent_system": "condenser_water_side"
    },
    "cw_temp": {
        "name": "冷卻水溫度 (CW Temp)",
        "icon": "🌡️",
        "unit": "°C",
        "description": "冷卻水側系統溫度：供水/回水/溫差",
        "pattern": "*CW*TEMP*,*CW*ST*,*CW*RT*,*CWS*,*CWR*",
        "parent_system": "condenser_water_side"
    },
    "cw_pressure": {
        "name": "冷卻水壓力 (CW Pressure)",
        "icon": "📊",
        "unit": "kPa",
        "description": "冷卻水側系統壓力：供水/回水/壓差",
        "pattern": "*CW*PRESSURE*,*CW*P*",
        "parent_system": "condenser_water_side"
    },
    "cw_flow": {
        "name": "冷卻水流量 (CW Flow)",
        "icon": "🌊",
        "unit": "LPM",
        "description": "冷卻水側系統總流量",
        "pattern": "*CW*FLOW*,*CW*LPM*",
        "parent_system": "condenser_water_side"
    },
    
    # === 冷卻水塔系統 (Cooling Tower) ===
    "cooling_tower": {
        "name": "冷卻水塔 (Cooling Tower)",
        "icon": "🏭",
        "unit": "Hz/kW/kWh/°C",
        "description": "冷卻水塔風扇：頻率、功率、用電量、狀態、趨近溫度",
        "pattern": "CT_*,TOWER*",
        "parent_system": "cooling_tower_system"
    },
    
    # === 環境參數 (Environment) ===
    "environment": {
        "name": "環境參數 (Environment)",
        "icon": "🌍",
        "unit": "°C/%",
        "description": "室外環境：外氣溫度、濕度、濕球溫度、焓值",
        "pattern": "OAT,OAH,WBT,OUTDOOR,AMB",
        "parent_system": "environment"
    },
    
    # === 系統層級 (System Level) - TARGET ===
    "system_level": {
        "name": "系統效率指標 (System Efficiency) 🎯",
        "icon": "⚡",
        "unit": "kW/kWh/kW/RT",
        "description": "TARGET: 系統總用電、COP、kW/RT 效率指標",
        "pattern": "*TOTAL*,*COP*,*KW*RT*,*EFFICIENCY*",
        "parent_system": "system_level",
        "is_target": True
    }
}


@dataclass
class FeatureMapping:
    """
    Enhanced feature mapping with support for dynamic categories.
    Organized by HVAC physical system hierarchy.
    
    Example:
        mapping = FeatureMapping(
            chiller_cols=["CH_0_RT", "CH_1_RT"],
            chw_pump_cols=["CHP_01_VFD_OUT"],
            scp_pump_cols=["SCP_01_VFD_OUT"],
            target_col="CH_SYS_TOTAL_KW",
            custom_categories={
                "chw_pressure": ["CHW_SUPPLY_P", "CHW_RETURN_P"],
            }
        )
    """
    
    # === 冰水側系統 (Chilled Water Side) ===
    chiller_cols: List[str] = field(default_factory=list)  # 冰水機：負載、溫度、流量、功率
    chw_pump_cols: List[str] = field(default_factory=list)  # 一次冰水泵
    scp_pump_cols: List[str] = field(default_factory=list)  # 二次側區域泵
    chw_temp_cols: List[str] = field(default_factory=list)  # 冰水溫度
    chw_pressure_cols: List[str] = field(default_factory=list)  # 冰水壓力
    chw_flow_cols: List[str] = field(default_factory=list)  # 冰水流量
    
    # === 冷卻水側系統 (Condenser Water Side) ===
    cw_pump_cols: List[str] = field(default_factory=list)  # 冷卻水泵
    cw_temp_cols: List[str] = field(default_factory=list)  # 冷卻水溫度
    cw_pressure_cols: List[str] = field(default_factory=list)  # 冷卻水壓力
    cw_flow_cols: List[str] = field(default_factory=list)  # 冷卻水流量
    
    # === 冷卻水塔系統 (Cooling Tower) ===
    cooling_tower_cols: List[str] = field(default_factory=list)  # 冷卻水塔
    
    # === 環境參數 (Environment) ===
    environment_cols: List[str] = field(default_factory=list)  # 外氣溫濕度
    
    # === 系統層級 (System Level) ===
    system_level_cols: List[str] = field(default_factory=list)  # 系統總用電、COP等
    
    # Target variable (要預測的目標，通常是 COP, kW/RT, 或總用電)
    target_col: str = "CH_SYS_TOTAL_KW"
    target_metric: str = "efficiency"  # "efficiency" (COP/kW/RT) or "power" (kW)
    
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
            # 冰水側系統
            "chiller": self.chiller_cols,
            "chw_pump": self.chw_pump_cols,
            "scp_pump": self.scp_pump_cols,
            "chw_temp": self.chw_temp_cols,
            "chw_pressure": self.chw_pressure_cols,
            "chw_flow": self.chw_flow_cols,
            # 冷卻水側系統
            "cw_pump": self.cw_pump_cols,
            "cw_temp": self.cw_temp_cols,
            "cw_pressure": self.cw_pressure_cols,
            "cw_flow": self.cw_flow_cols,
            # 冷卻水塔
            "cooling_tower": self.cooling_tower_cols,
            # 環境
            "environment": self.environment_cols,
            # 系統層級
            "system_level": self.system_level_cols,
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
        
        # Standard categories - HVAC physical system hierarchy
        category_map = {
            # 冰水側系統
            "chiller": self.chiller_cols,
            "chw_pump": self.chw_pump_cols,
            "scp_pump": self.scp_pump_cols,
            "chw_temp": self.chw_temp_cols,
            "chw_pressure": self.chw_pressure_cols,
            "chw_flow": self.chw_flow_cols,
            # 冷卻水側系統
            "cw_pump": self.cw_pump_cols,
            "cw_temp": self.cw_temp_cols,
            "cw_pressure": self.cw_pressure_cols,
            "cw_flow": self.cw_flow_cols,
            # 冷卻水塔
            "cooling_tower": self.cooling_tower_cols,
            # 環境
            "environment": self.environment_cols,
            # 系統層級
            "system_level": self.system_level_cols,
            # 向後相容
            "load": self.chiller_cols,
            "chw_pump_hz_cols": self.chw_pump_cols,
            "cw_pump_hz_cols": self.cw_pump_cols,
            "ct_fan_hz_cols": self.cooling_tower_cols,
            "temp_cols": self.chw_temp_cols,
            "env_cols": self.environment_cols,
        }
        
        return category_map.get(category_id, [])
    
    def set_category_columns(self, category_id: str, columns: List[str]):
        """Set columns for a category (creates custom category if not standard)."""
        # Standard categories - HVAC physical system hierarchy
        standard_setters = {
            # 冰水側系統
            "chiller": lambda x: setattr(self, 'chiller_cols', x),
            "chw_pump": lambda x: setattr(self, 'chw_pump_cols', x),
            "scp_pump": lambda x: setattr(self, 'scp_pump_cols', x),
            "chw_temp": lambda x: setattr(self, 'chw_temp_cols', x),
            "chw_pressure": lambda x: setattr(self, 'chw_pressure_cols', x),
            "chw_flow": lambda x: setattr(self, 'chw_flow_cols', x),
            # 冷卻水側系統
            "cw_pump": lambda x: setattr(self, 'cw_pump_cols', x),
            "cw_temp": lambda x: setattr(self, 'cw_temp_cols', x),
            "cw_pressure": lambda x: setattr(self, 'cw_pressure_cols', x),
            "cw_flow": lambda x: setattr(self, 'cw_flow_cols', x),
            # 冷卻水塔
            "cooling_tower": lambda x: setattr(self, 'cooling_tower_cols', x),
            # 環境
            "environment": lambda x: setattr(self, 'environment_cols', x),
            # 系統層級
            "system_level": lambda x: setattr(self, 'system_level_cols', x),
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
        
        # Determine required vs optional based on category importance
        # Required: chiller (load), target
        # Optional: others
        required_categories = ["chiller", "system_level"]  # system_level contains target
        
        missing_required = []
        missing_optional = []
        
        for cat_id in missing_by_category:
            if cat_id in required_categories:
                missing_required.extend(missing_by_category[cat_id])
            else:
                missing_optional.extend(missing_by_category[cat_id])
        
        return {
            "matched": matched,
            "missing": missing,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "missing_by_category": missing_by_category,
            "available_in_df": [col for col in df_columns if col not in all_mapped],
            "match_rate": len(matched) / len(all_mapped) if all_mapped else 0
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            # 新架構欄位
            "chiller_cols": self.chiller_cols,
            "chw_pump_cols": self.chw_pump_cols,
            "scp_pump_cols": self.scp_pump_cols,
            "chw_temp_cols": self.chw_temp_cols,
            "chw_pressure_cols": self.chw_pressure_cols,
            "chw_flow_cols": self.chw_flow_cols,
            "cw_pump_cols": self.cw_pump_cols,
            "cw_temp_cols": self.cw_temp_cols,
            "cw_pressure_cols": self.cw_pressure_cols,
            "cw_flow_cols": self.cw_flow_cols,
            "cooling_tower_cols": self.cooling_tower_cols,
            "environment_cols": self.environment_cols,
            "system_level_cols": self.system_level_cols,
            "target_col": self.target_col,
            "target_metric": self.target_metric,
            "custom_categories": self.custom_categories,
            "category_metadata": self.category_metadata,
            # 向後相容欄位
            "load_cols": self.chiller_cols,
            "chw_pump_hz_cols": self.chw_pump_cols,
            "cw_pump_hz_cols": self.cw_pump_cols,
            "ct_fan_hz_cols": self.cooling_tower_cols,
            "temp_cols": self.chw_temp_cols,
            "env_cols": self.environment_cols,
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
        # HVAC Physical System Hierarchy - Auto-detection patterns
        # Each category has (display_name, [list_of_patterns])
        patterns = {
            # === 冰水側系統 ===
            "chiller": ("冰水機", [
                "CH_", "CHILLER", "CHILLER_",  # 冰水機本體 (但排除 CH_SYS)
                "RT", "TON", "Tons",  # 噸數負載
                "EVAP", "EVAPORATOR", "COND", "CONDENSER",  # 蒸發器、冷凝器
            ]),
            "chw_pump": ("冰水泵", [
                "CHP", "CHWP", "CHILLED_PUMP",
                "CHWP_", "CHP_",
            ]),
            "scp_pump": ("區域泵", [
                "SCP", "SECONDARY", "SEC_CHP",
                "SCP_", "SECONDARY_PUMP",
            ]),
            "chw_temp": ("冰水溫度", [
                "CHW_TEMP", "CHWT", "CHW_ST", "CHW_RT",
                "CHW_SUPPLY", "CHW_RETURN", "CHW_DELTA",
                "EVAP_TEMP", "EVAP_WATER",
            ]),
            "chw_pressure": ("冰水壓力", [
                "CHW_PRESSURE", "CHW_P", "CHWPRESS",
                "CHW_HEAD", "CHW_DELTA_P",
            ]),
            "chw_flow": ("冰水流量", [
                "CHW_FLOW", "CHWFLOW", "CHW_LPM", "CHW_GPM",
                "EVAP_FLOW", "CHW_RATE",
            ]),
            
            # === 冷卻水側系統 ===
            "cw_pump": ("冷卻水泵", [
                "CWP", "CWPUMP", "COND_PUMP", "CONDENSER_PUMP",
                "CWP_", "CW_PUMP",
            ]),
            "cw_temp": ("冷卻水溫度", [
                "CW_TEMP", "CWT", "CWS", "CWR",
                "CW_SUPPLY", "CW_RETURN", "CW_DELTA",
                "COND_TEMP", "COND_WATER", "CONDENSER_TEMP",
            ]),
            "cw_pressure": ("冷卻水壓力", [
                "CW_PRESSURE", "CW_P", "CWPRESS",
                "CW_HEAD", "CW_DELTA_P",
            ]),
            "cw_flow": ("冷卻水流量", [
                "CW_FLOW", "CWFLOW", "CW_LPM", "CW_GPM",
                "COND_FLOW", "CW_RATE",
            ]),
            
            # === 冷卻水塔 ===
            "cooling_tower": ("冷卻水塔", [
                "CT_", "COOLING_TOWER", "TOWER",
                "CTFAN", "CT_FAN", "TOWER_FAN",
            ]),
            
            # === 環境參數 ===
            "environment": ("環境參數", [
                "OAT", "OUTDOOR", "OA_TEMP", "AMBIENT",
                "OAH", "RH", "HUMIDITY", "RELATIVE_HUMID",
                "WBT", "WET_BULB", "WB_TEMP",
                "ENTHALPY", "H_AIR",
            ]),
            
            # === 系統層級 ===
            "system_level": ("系統層級", [
                "TOTAL", "SYSTEM", "PLANT",
                "COP", "EFFICIENCY", "KW_RT", "KW/RT",
            ]),
        }
        
        # Override with custom patterns if provided
        if auto_patterns:
            patterns.update(auto_patterns)
        
        # Auto-detect columns for each category
        category_columns = {}
        
        # Category-specific exclusion rules
        exclusion_rules = {
            "chiller": ["CH_SYS", "SYSTEM", "TOTAL"],  # 排除系統級欄位
        }
        
        for cat_id, (name, pattern_list) in patterns.items():
            matched_cols = []
            for col in df_columns:
                col_upper = col.upper()
                # Check if any pattern matches
                if any(p.upper() in col_upper for p in pattern_list):
                    # General exclusions (frozen flags, alarms)
                    if any(exclude in col_upper for exclude in ["FROZEN", "FLAG", "ALARM", "FAULT", "ERROR"]):
                        continue
                    # Category-specific exclusions
                    if cat_id in exclusion_rules:
                        if any(excl in col_upper for excl in exclusion_rules[cat_id]):
                            continue
                    matched_cols.append(col)
            
            if matched_cols:
                category_columns[cat_id] = sorted(set(matched_cols))
        
        # Create mapping with detected columns
        mapping = cls(
            # 冰水側系統
            chiller_cols=category_columns.get("chiller", []),
            chw_pump_cols=category_columns.get("chw_pump", []),
            scp_pump_cols=category_columns.get("scp_pump", []),
            chw_temp_cols=category_columns.get("chw_temp", []),
            chw_pressure_cols=category_columns.get("chw_pressure", []),
            chw_flow_cols=category_columns.get("chw_flow", []),
            # 冷卻水側系統
            cw_pump_cols=category_columns.get("cw_pump", []),
            cw_temp_cols=category_columns.get("cw_temp", []),
            cw_pressure_cols=category_columns.get("cw_pressure", []),
            cw_flow_cols=category_columns.get("cw_flow", []),
            # 冷卻水塔
            cooling_tower_cols=category_columns.get("cooling_tower", []),
            # 環境
            environment_cols=category_columns.get("environment", []),
            # 系統層級
            system_level_cols=category_columns.get("system_level", []),
        )
        
        # Auto-detect target (優先找效率指標，其次找總用電)
        target_candidates = []
        # 1. 優先找 COP 相關
        target_candidates = [c for c in df_columns if "COP" in c.upper()]
        # 2. 其次找 kW/RT 效率指標
        if not target_candidates:
            target_candidates = [c for c in df_columns if any(x in c.upper() for x in ["KW_RT", "KW/RT", "KW_PER_RT", "EFFICIENCY"])]
        # 3. 最後找總用電
        if not target_candidates:
            target_candidates = [c for c in df_columns if "TOTAL" in c.upper() and "KW" in c.upper()]
        if not target_candidates:
            target_candidates = [c for c in df_columns if c.upper().endswith("_KW")]
        
        if target_candidates:
            mapping.target_col = target_candidates[0]
            # 判斷 target 類型
            if any(x in mapping.target_col.upper() for x in ["COP", "EFFICIENCY", "KW_RT", "KW/RT"]):
                mapping.target_metric = "efficiency"
            else:
                mapping.target_metric = "power"
        
        logger.info(f"Auto-created mapping with {len(mapping.get_all_feature_cols())} features, target: {mapping.target_col}")
        return mapping
    
    @staticmethod
    def match_columns_by_pattern(columns: List[str], pattern: str) -> List[str]:
        """
        Match columns using wildcard pattern (glob style).
        
        Supports:
            - * : matches any sequence of characters (including empty)
            - ? : matches any single character
            - [seq] : matches any character in seq
            - [!seq] : matches any character not in seq
        
        Args:
            columns: List of column names to match against
            pattern: Glob pattern (e.g., "*_RT", "CHP*VFD_OUT", "CWP_*_VFD_OUT")
            
        Returns:
            List of matched column names
            
        Examples:
            >>> FeatureMapping.match_columns_by_pattern(
            ...     ["CH_0_RT", "CH_1_RT", "CHP_01_VFD_OUT"], "*_RT")
            ['CH_0_RT', 'CH_1_RT']
            
            >>> FeatureMapping.match_columns_by_pattern(
            ...     ["CHP_01_VFD_OUT", "CHP_02_VFD_OUT", "CWP_01_VFD_OUT"], "CHP*VFD_OUT")
            ['CHP_01_VFD_OUT', 'CHP_02_VFD_OUT']
        """
        matched = [col for col in columns if fnmatch.fnmatch(col, pattern)]
        return matched
    
    @classmethod
    def create_from_wildcard_patterns(
        cls,
        df_columns: List[str],
        wildcard_patterns: Dict[str, Union[str, List[str]]],
        target_pattern: str = "*TOTAL*KW"
    ) -> "FeatureMapping":
        """
        Create mapping from wildcard patterns.
        
        Args:
            df_columns: List of column names from dataframe
            wildcard_patterns: Dict mapping category_id to pattern(s)
                Example: {
                    "load": "*_RT",
                    "chw_pump": "CHP*VFD_OUT",
                    "cw_pump": "CWP*VFD_OUT",
                    "ct_fan": "CT_*_VFD_OUT"
                }
            target_pattern: Pattern to match target column (default: "*TOTAL*KW")
            
        Returns:
            FeatureMapping instance with matched columns
            
        Example:
            >>> mapping = FeatureMapping.create_from_wildcard_patterns(
            ...     columns=["CH_0_RT", "CH_1_RT", "CHP_01_VFD_OUT", "CH_SYS_TOTAL_KW"],
            ...     wildcard_patterns={
            ...         "load": "*_RT",
            ...         "chw_pump": "CHP*VFD_OUT"
            ...     }
            ... )
        """
        category_columns = {}
        
        for cat_id, patterns in wildcard_patterns.items():
            matched_cols = []
            
            # Handle both single pattern and list of patterns
            if isinstance(patterns, str):
                patterns = [patterns]
            
            for pattern in patterns:
                matched = cls.match_columns_by_pattern(df_columns, pattern)
                matched_cols.extend(matched)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_cols = []
            for col in matched_cols:
                if col not in seen:
                    seen.add(col)
                    unique_cols.append(col)
            
            if unique_cols:
                category_columns[cat_id] = unique_cols
                logger.info(f"Pattern '{patterns}' matched {len(unique_cols)} columns for '{cat_id}'")
        
        # Create mapping with matched columns - HVAC Physical System Hierarchy
        mapping = cls(
            # 冰水側系統
            chiller_cols=category_columns.get("chiller", []),
            chw_pump_cols=category_columns.get("chw_pump", []),
            scp_pump_cols=category_columns.get("scp_pump", []),
            chw_temp_cols=category_columns.get("chw_temp", []),
            chw_pressure_cols=category_columns.get("chw_pressure", []),
            chw_flow_cols=category_columns.get("chw_flow", []),
            # 冷卻水側系統
            cw_pump_cols=category_columns.get("cw_pump", []),
            cw_temp_cols=category_columns.get("cw_temp", []),
            cw_pressure_cols=category_columns.get("cw_pressure", []),
            cw_flow_cols=category_columns.get("cw_flow", []),
            # 冷卻水塔
            cooling_tower_cols=category_columns.get("cooling_tower", []),
            # 環境
            environment_cols=category_columns.get("environment", []),
            # 系統層級
            system_level_cols=category_columns.get("system_level", []),
        )
        
        # Add any unmatched categories as custom
        standard_cats = ["chiller", "chw_pump", "scp_pump", "chw_temp", "chw_pressure", "chw_flow",
                        "cw_pump", "cw_temp", "cw_pressure", "cw_flow", 
                        "cooling_tower", "environment", "system_level"]
        mapping.custom_categories = {k: v for k, v in category_columns.items() if k not in standard_cats}
        
        # Auto-detect target using pattern
        target_candidates = cls.match_columns_by_pattern(df_columns, target_pattern)
        if target_candidates:
            mapping.target_col = target_candidates[0]
            logger.info(f"Target column matched: {mapping.target_col}")
        
        total_features = len(mapping.get_all_feature_cols())
        logger.info(f"Wildcard mapping created with {total_features} features across {len(category_columns)} categories")
        
        return mapping


# Predefined mappings with new HVAC hierarchy
PREDEFINED_MAPPINGS = {
    "default": FeatureMapping.create_from_dataframe([
        # 冰水機
        "CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT",
        # 冰水泵
        "CHP_01_VFD_OUT", "CHP_02_VFD_OUT",
        # 冷卻水泵
        "CWP_01_VFD_OUT", "CWP_02_VFD_OUT",
        # 冷卻水塔
        "CT_01_VFD_OUT", "CT_02_VFD_OUT",
        # 環境
        "CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT",
        # Target
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
