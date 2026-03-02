"""
控制語意管理器 (Control Semantics Manager) v1.4

負責管理控制對（Sensor-Setpoint 配對），支援：
- 自動識別控制對
- 控制偏差計算
- 控制穩定度分析

錯誤代碼:
- E420: Control Semantics 版本不符
- E421: Control Pair 不完整
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from src.utils.logger import get_logger


class ControlSemanticType(str, Enum):
    """控制語意類型"""
    ON_OFF = "on_off"
    VARIABLE_SPEED = "variable_speed"
    VALVE_POSITION = "valve_position"
    SETPOINT = "setpoint"
    FEEDBACK = "feedback"
    NONE = "none"


@dataclass
class ControlPair:
    """控制對資料類別"""
    sensor_column: str      # 感測器欄位
    setpoint_column: str    # 設定點欄位
    equipment_id: str       # 所屬設備
    control_type: str       # 控制類型
    physical_type: str      # 物理類型 (temperature/pressure/etc)
    
    def __repr__(self):
        return f"ControlPair({self.equipment_id}: {self.sensor_column} -> {self.setpoint_column})"


class ControlSemanticsManager:
    """
    控制語意管理器 v1.4
    
    從 FeatureAnnotationManager 讀取控制語意資訊，
    識別 Sensor-Setpoint 配對，供控制偏差特徵生成使用。
    """
    
    def __init__(self, annotation_manager):
        """
        初始化控制語意管理器
        
        Args:
            annotation_manager: FeatureAnnotationManager 實例
        """
        self.annotation_manager = annotation_manager
        self.logger = get_logger("ControlSemanticsManager")
        
        # 控制對列表
        self._control_pairs: List[ControlPair] = []
        self._control_pairs_by_equipment: Dict[str, List[ControlPair]] = {}
        
        # 建立控制對
        self._build_control_pairs()
        
        self.logger.info(
            f"ControlSemanticsManager 初始化完成: "
            f"控制對數={len(self._control_pairs)}"
        )
    
    def _build_control_pairs(self):
        """
        從 AnnotationManager 建立控制對
        
        識別規則：
        1. 明確標註 control_semantic 為 setpoint/feedback 的欄位
        2. 從欄位命名推斷（如 xxx_sp, xxx_setpoint 對應 xxx 感測器）
        """
        try:
            all_columns = self.annotation_manager.get_all_columns()
            
            # 收集所有欄位資訊
            column_info = {}
            for col_name in all_columns:
                anno = self.annotation_manager.get_column_annotation(col_name)
                if not anno:
                    continue
                
                control_semantic = getattr(anno, 'control_semantic', None)
                eq_id = getattr(anno, 'equipment_id', None)
                physical_type = getattr(anno, 'physical_type', None)
                
                column_info[col_name] = {
                    'control_semantic': control_semantic,
                    'equipment_id': eq_id,
                    'physical_type': physical_type
                }
            
            # 策略 1: 從明確標註建立控制對
            self._build_from_explicit_annotation(column_info)
            
            # 策略 2: 從命名慣例推斷
            self._build_from_naming_convention(column_info)
            
            # 建立設備索引
            for pair in self._control_pairs:
                if pair.equipment_id not in self._control_pairs_by_equipment:
                    self._control_pairs_by_equipment[pair.equipment_id] = []
                self._control_pairs_by_equipment[pair.equipment_id].append(pair)
                
        except Exception as e:
            self.logger.warning(f"建立控制對時發生錯誤: {e}")
    
    def _build_from_explicit_annotation(self, column_info: Dict):
        """從明確標註建立控制對"""
        # 找出所有 setpoint 和 feedback
        setpoints = []
        feedbacks = []
        
        for col_name, info in column_info.items():
            semantic = info.get('control_semantic')
            if semantic == 'setpoint':
                setpoints.append((col_name, info))
            elif semantic == 'feedback':
                feedbacks.append((col_name, info))
        
        # 配對：同一設備、同一 physical_type
        for sp_col, sp_info in setpoints:
            sp_eq = sp_info.get('equipment_id')
            sp_type = sp_info.get('physical_type')
            
            for fb_col, fb_info in feedbacks:
                fb_eq = fb_info.get('equipment_id')
                fb_type = fb_info.get('physical_type')
                
                # 同一設備且同一物理類型
                if sp_eq == fb_eq and sp_eq and sp_type == fb_type:
                    pair = ControlPair(
                        sensor_column=fb_col,
                        setpoint_column=sp_col,
                        equipment_id=sp_eq,
                        control_type="feedback_control",
                        physical_type=sp_type or "unknown"
                    )
                    self._control_pairs.append(pair)
                    self.logger.debug(f"建立控制對: {pair}")
    
    def _build_from_naming_convention(self, column_info: Dict):
        """從命名慣例建立控制對"""
        # 識別 setpoint 命名模式
        sp_patterns = ['_sp', '_setpoint', '_set', '_target']
        
        for col_name, info in column_info.items():
            col_lower = col_name.lower()
            
            # 檢查是否為 setpoint 欄位
            is_setpoint = any(col_lower.endswith(p) or f"{p}_" in col_lower 
                            for p in sp_patterns)
            
            if is_setpoint:
                # 嘗試找到對應的感測器欄位
                base_name = self._extract_base_name(col_name, sp_patterns)
                
                # 尋找匹配的感測器欄位
                for sensor_col, sensor_info in column_info.items():
                    if sensor_col == col_name:
                        continue
                    
                    sensor_base = sensor_col.lower().replace('_sensor', '').replace('_pv', '')
                    
                    # 匹配規則：基礎名稱相同，且不是 setpoint
                    if (sensor_base == base_name or 
                        sensor_col.lower() == base_name or
                        sensor_col.lower().replace('_', '') == base_name.replace('_', '')):
                        
                        sensor_semantic = sensor_info.get('control_semantic')
                        if sensor_semantic not in ['setpoint', None]:
                            continue  # 跳過其他 setpoint
                        
                        eq_id = info.get('equipment_id') or sensor_info.get('equipment_id')
                        physical_type = info.get('physical_type') or sensor_info.get('physical_type')
                        
                        # 檢查是否已存在相同配對
                        existing = [p for p in self._control_pairs 
                                   if p.sensor_column == sensor_col and p.setpoint_column == col_name]
                        if not existing:
                            pair = ControlPair(
                                sensor_column=sensor_col,
                                setpoint_column=col_name,
                                equipment_id=eq_id or "unknown",
                                control_type="feedback_control",
                                physical_type=physical_type or "unknown"
                            )
                            self._control_pairs.append(pair)
                            self.logger.debug(f"從命名建立控制對: {pair}")
                        break
    
    def _extract_base_name(self, col_name: str, patterns: List[str]) -> str:
        """
        從 setpoint 欄位名稱提取基礎名稱
        
        Args:
            col_name: 欄位名稱
            patterns: setpoint 模式列表
            
        Returns:
            基礎名稱
        """
        col_lower = col_name.lower()
        
        for pattern in patterns:
            if col_lower.endswith(pattern):
                return col_lower[:-len(pattern)]
            elif f"{pattern}_" in col_lower:
                return col_lower.split(f"{pattern}_")[0]
        
        return col_lower
    
    def get_pair_count(self) -> int:
        """取得控制對數量"""
        return len(self._control_pairs)
    
    def get_all_pairs(self) -> List[ControlPair]:
        """取得所有控制對"""
        return self._control_pairs.copy()
    
    def get_pairs_by_equipment(self, equipment_id: str) -> List[ControlPair]:
        """
        取得指定設備的控制對
        
        Args:
            equipment_id: 設備 ID
            
        Returns:
            控制對列表
        """
        return self._control_pairs_by_equipment.get(equipment_id, [])
    
    def get_pairs_by_physical_type(self, physical_type: str) -> List[ControlPair]:
        """
        取得指定物理類型的控制對
        
        Args:
            physical_type: 物理類型
            
        Returns:
            控制對列表
        """
        return [p for p in self._control_pairs if p.physical_type == physical_type]
    
    def is_control_pair(self, sensor_col: str, setpoint_col: str) -> bool:
        """
        檢查是否為控制對
        
        Args:
            sensor_col: 感測器欄位
            setpoint_col: 設定點欄位
            
        Returns:
            是否為控制對
        """
        return any(p.sensor_column == sensor_col and p.setpoint_column == setpoint_col 
                  for p in self._control_pairs)
    
    def get_control_semantics_info(self) -> Dict[str, Any]:
        """
        取得完整的控制語意資訊
        
        Returns:
            控制語意資訊字典
        """
        return {
            "control_pairs": [
                {
                    "sensor": p.sensor_column,
                    "setpoint": p.setpoint_column,
                    "equipment_id": p.equipment_id,
                    "control_type": p.control_type,
                    "physical_type": p.physical_type
                }
                for p in self._control_pairs
            ],
            "pairs_by_equipment": {
                eq_id: len(pairs)
                for eq_id, pairs in self._control_pairs_by_equipment.items()
            },
            "total_pairs": len(self._control_pairs)
        }
