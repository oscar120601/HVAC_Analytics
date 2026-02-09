"""
Feature Mapping Configuration System.

Allows users to define custom mappings from their monitoring point names
to model feature categories (load, pump frequencies, temperatures, etc.)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class FeatureMapping:
    """
    Maps monitoring point names to feature categories.
    
    Example:
        mapping = FeatureMapping(
            load_cols=["CH_0_RT", "CH_1_RT"],           # 負載 (RT)
            chw_pump_hz_cols=["CHP_01_VFD_OUT"],        # 冷凍泵頻率
            cw_pump_hz_cols=["CWP_01_VFD_OUT"],         # 冷卻泵頻率  
            ct_fan_hz_cols=["CT_01_VFD_OUT"],           # 冷卻塔風扇頻率
            temp_cols=["CH_0_SWT", "CH_0_RWT"],         # 溫度
            env_cols=["CT_SYS_OAT", "CT_SYS_OAH"],      # 環境參數
            target_col="CH_SYS_TOTAL_KW"                # 目標 (耗電量)
        )
    """
    # Feature categories
    load_cols: List[str]              # 冷凍機負載 (RT)
    chw_pump_hz_cols: List[str]       # 冷凍水幫浦頻率 (Hz)
    cw_pump_hz_cols: List[str]        # 冷卻水幫浦頻率 (Hz)
    ct_fan_hz_cols: List[str]         # 冷卻塔風扇頻率 (Hz)
    temp_cols: List[str]              # 溫度相關 (°C)
    env_cols: List[str]               # 環境參數 (外氣溫度/濕度/濕球)
    
    # Target variable
    target_col: str = "CH_SYS_TOTAL_KW"
    
    # Optional: Custom feature groups
    custom_features: Optional[Dict[str, List[str]]] = None
    
    def __post_init__(self):
        """Validate the mapping configuration."""
        # Handle backward compatibility: if env_cols not provided, use empty list
        if not hasattr(self, 'env_cols') or self.env_cols is None:
            self.env_cols = []
        
        all_cols = (
            self.load_cols +
            self.chw_pump_hz_cols +
            self.cw_pump_hz_cols +
            self.ct_fan_hz_cols +
            self.temp_cols +
            self.env_cols
        )
        
        # Check for duplicates
        seen = set()
        duplicates = []
        for col in all_cols:
            if col in seen:
                duplicates.append(col)
            seen.add(col)
        
        if duplicates:
            logger.warning(f"Duplicate columns in mapping: {duplicates}")
    
    def get_all_feature_cols(self) -> List[str]:
        """Get all feature column names (excluding target)."""
        env_cols = getattr(self, 'env_cols', [])
        return (
            self.load_cols +
            self.chw_pump_hz_cols +
            self.cw_pump_hz_cols +
            self.ct_fan_hz_cols +
            self.temp_cols +
            env_cols
        )
    
    def get_category_for_column(self, col_name: str) -> Optional[str]:
        """Get the category name for a given column."""
        env_cols = getattr(self, 'env_cols', [])
        if col_name in self.load_cols:
            return "load"
        elif col_name in self.chw_pump_hz_cols:
            return "chw_pump"
        elif col_name in self.cw_pump_hz_cols:
            return "cw_pump"
        elif col_name in self.ct_fan_hz_cols:
            return "ct_fan"
        elif col_name in self.temp_cols:
            return "temperature"
        elif col_name in env_cols:
            return "environment"
        elif self.custom_features and col_name in [c for cols in self.custom_features.values() for c in cols]:
            for cat, cols in self.custom_features.items():
                if col_name in cols:
                    return cat
        return None
    
    def validate_against_dataframe(self, df_columns: List[str]) -> Dict[str, List[str]]:
        """
        Validate mapping against actual dataframe columns.
        
        Returns:
            Dict with 'matched', 'missing_required', 'missing_optional' keys
        """
        all_mapped = self.get_all_feature_cols()
        
        matched = [col for col in all_mapped if col in df_columns]
        missing = [col for col in all_mapped if col not in df_columns]
        
        # Determine if missing columns are critical
        # Load and target are required, others are optional
        missing_required = []
        missing_optional = []
        
        for col in missing:
            if col in self.load_cols or col == self.target_col:
                missing_required.append(col)
            else:
                missing_optional.append(col)
        
        return {
            "matched": matched,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "available_in_df": [col for col in df_columns if col not in all_mapped]
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
    
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
        load_pattern: str = "RT",
        chw_pattern: str = "CHP",
        cw_pattern: str = "CWP", 
        ct_pattern: str = "CT_",
        temp_patterns: List[str] = None,
        env_patterns: List[str] = None
    ) -> "FeatureMapping":
        """
        Auto-create mapping from dataframe columns using pattern matching.
        
        Args:
            df_columns: List of column names from dataframe
            load_pattern: Pattern to identify load columns (default: "RT")
            chw_pattern: Pattern for chilled water pumps (default: "CHP")
            cw_pattern: Pattern for cooling water pumps (default: "CWP")
            ct_pattern: Pattern for cooling tower fans (default: "CT_")
            temp_patterns: Patterns for temperature columns
            env_patterns: Patterns for environment parameters (OAT, OAH, WBT)
        """
        if temp_patterns is None:
            temp_patterns = ["SWT", "RWT", "TEMP"]
        if env_patterns is None:
            env_patterns = ["OAT", "OAH", "WBT", "OUTDOOR", "AMB"]  # 外氣溫度/濕度/濕球
        
        load_cols = [c for c in df_columns if load_pattern in c and "KW" not in c]
        chw_pump_hz_cols = [c for c in df_columns if chw_pattern in c and "VFD" in c]
        cw_pump_hz_cols = [c for c in df_columns if cw_pattern in c and "VFD" in c]
        ct_fan_hz_cols = [c for c in df_columns if ct_pattern in c and "VFD" in c]
        
        temp_cols = []
        for c in df_columns:
            if any(p in c for p in temp_patterns):
                # Exclude VFD outputs and environment temp from process temp
                if "VFD" not in c and not any(ep in c for ep in env_patterns):
                    temp_cols.append(c)
        
        # Auto-detect environment parameters (OAT, OAH, WBT)
        env_cols = []
        for c in df_columns:
            if any(p in c for p in env_patterns):
                env_cols.append(c)
        
        # Auto-detect target column
        target_col = "CH_SYS_TOTAL_KW"
        if target_col not in df_columns:
            # Try to find any column with TOTAL_KW or _KW
            kw_cols = [c for c in df_columns if "TOTAL" in c and "KW" in c]
            if kw_cols:
                target_col = kw_cols[0]
            else:
                kw_cols = [c for c in df_columns if c.endswith("_KW")]
                if kw_cols:
                    target_col = kw_cols[0]
        
        mapping = cls(
            load_cols=sorted(load_cols),
            chw_pump_hz_cols=sorted(chw_pump_hz_cols),
            cw_pump_hz_cols=sorted(cw_pump_hz_cols),
            ct_fan_hz_cols=sorted(ct_fan_hz_cols),
            temp_cols=sorted(temp_cols),
            env_cols=sorted(env_cols),
            target_col=target_col
        )
        
        logger.info(f"Auto-created mapping from {len(df_columns)} columns:")
        logger.info(f"  Load (RT): {len(load_cols)} columns")
        logger.info(f"  CHW Pumps: {len(chw_pump_hz_cols)} columns")
        logger.info(f"  CW Pumps: {len(cw_pump_hz_cols)} columns")
        logger.info(f"  CT Fans: {len(ct_fan_hz_cols)} columns")
        logger.info(f"  Temperatures: {len(temp_cols)} columns")
        logger.info(f"  Environment: {len(env_cols)} columns {env_cols}")
        logger.info(f"  Target: {target_col}")
        
        return mapping


# Predefined mappings for common naming conventions
PREDEFINED_MAPPINGS = {
    "default": FeatureMapping(
        load_cols=["CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT"],
        chw_pump_hz_cols=[
            "CHP_01_VFD_OUT", "CHP_02_VFD_OUT", "CHP_03_VFD_OUT",
            "CHP_04_VFD_OUT", "CHP_05_VFD_OUT"
        ],
        cw_pump_hz_cols=[
            "CWP_01_VFD_OUT", "CWP_02_VFD_OUT", "CWP_03_VFD_OUT",
            "CWP_04_VFD_OUT", "CWP_05_VFD_OUT"
        ],
        ct_fan_hz_cols=[
            "CT_01_VFD_OUT", "CT_02_VFD_OUT", "CT_03_VFD_OUT",
            "CT_04_VFD_OUT", "CT_05_VFD_OUT"
        ],
        temp_cols=[
            "CH_0_SWT", "CH_0_RWT",
            "CW_SYS_SWT", "CW_SYS_RWT"
        ],
        env_cols=[
            "CT_SYS_OAT",   # 外氣溫度
            "CT_SYS_OAH",   # 外氣濕度
            "CT_SYS_WBT"    # 外氣濕球溫度
        ],
        target_col="CH_SYS_TOTAL_KW"
    ),
    
    "cgmh_ty": FeatureMapping(
        load_cols=["CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT"],
        chw_pump_hz_cols=[
            "CHP_01_VFD_OUT", "CHP_02_VFD_OUT", "CHP_03_VFD_OUT",
            "CHP_04_VFD_OUT", "CHP_05_VFD_OUT"
        ],
        cw_pump_hz_cols=[
            "CWP_01_VFD_OUT", "CWP_02_VFD_OUT", "CWP_03_VFD_OUT",
            "CWP_04_VFD_OUT", "CWP_05_VFD_OUT"
        ],
        ct_fan_hz_cols=[
            "CT_01_VFD_OUT", "CT_02_VFD_OUT", "CT_03_VFD_OUT",
            "CT_04_VFD_OUT", "CT_05_VFD_OUT"
        ],
        temp_cols=[
            "CH_0_SWT", "CH_0_RWT",
            "CW_SYS_SWT", "CW_SYS_RWT"
        ],
        env_cols=[
            "CT_SYS_OAT",   # 外氣溫度
            "CT_SYS_OAH",   # 外氣濕度
            "CT_SYS_WBT"    # 外氣濕球溫度
        ],
        target_col="CH_SYS_TOTAL_KW"
    ),
    
    # Example: Alternative naming convention
    "alternative_01": FeatureMapping(
        load_cols=["CHILLER_01_LOAD", "CHILLER_02_LOAD", "CHILLER_03_LOAD"],
        chw_pump_hz_cols=["CHWP_01_HZ", "CHWP_02_HZ", "CHWP_03_HZ"],
        cw_pump_hz_cols=["CWP_01_HZ", "CWP_02_HZ", "CWP_03_HZ"],
        ct_fan_hz_cols=["CTF_01_HZ", "CTF_02_HZ", "CTF_03_HZ"],
        temp_cols=["SUPPLY_TEMP", "RETURN_TEMP"],
        env_cols=["OUTDOOR_TEMP", "OUTDOOR_HUMIDITY", "WET_BULB_TEMP"],
        target_col="TOTAL_POWER_KW"
    )
}


def get_feature_mapping(name_or_path: str = "default") -> FeatureMapping:
    """
    Get feature mapping by name or load from file.
    
    Args:
        name_or_path: 
            - "default", "cgmh_ty", etc. → Use predefined mapping
            - "path/to/mapping.json" → Load from JSON file
    
    Returns:
        FeatureMapping instance
    """
    # Check if it's a predefined mapping
    if name_or_path in PREDEFINED_MAPPINGS:
        logger.info(f"Using predefined mapping: {name_or_path}")
        return PREDEFINED_MAPPINGS[name_or_path]
    
    # Check if it's a file path
    path = Path(name_or_path)
    if path.exists() and path.suffix == '.json':
        logger.info(f"Loading mapping from file: {name_or_path}")
        return FeatureMapping.load(name_or_path)
    
    # Default fallback
    logger.warning(f"Unknown mapping '{name_or_path}', using default")
    return PREDEFINED_MAPPINGS["default"]


if __name__ == "__main__":
    # Example usage and testing
    
    # 1. Use predefined mapping
    mapping = get_feature_mapping("default")
    print("Default mapping:")
    print(f"  Load columns: {mapping.load_cols}")
    print(f"  Target: {mapping.target_col}")
    
    # 2. Create from dataframe columns
    sample_columns = [
        "timestamp", "CH_0_RT", "CH_1_RT", "CHP_01_VFD_OUT",
        "CWP_01_VFD_OUT", "CT_01_VFD_OUT", "CH_SYS_TOTAL_KW"
    ]
    auto_mapping = FeatureMapping.create_from_dataframe(sample_columns)
    print("\nAuto-created mapping:")
    print(f"  Features: {auto_mapping.get_all_feature_cols()}")
    
    # 3. Save and load
    auto_mapping.save("/tmp/test_mapping.json")
    loaded = FeatureMapping.load("/tmp/test_mapping.json")
    print(f"\nLoaded mapping matches: {loaded.to_dict() == auto_mapping.to_dict()}")
