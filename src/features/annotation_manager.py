"""
Feature Annotation Manager

特徵標註管理器 - 提供唯讀特徵標註查詢功能

設計原則:
1. 唯讀介面：提供查詢方法，禁止修改 YAML
2. SSOT 存取：所有資料來自 config/features/sites/{site_id}.yaml
3. 快取機制：YAML 載入後快取於記憶體，避免重複 I/O
4. HVAC 感知：支援設備互鎖查詢與驗證
5. 時間基準感知：支援 TemporalContext 傳遞

錯誤代碼:
- E400: Schema 版本不符
- E402: 找不到案場標註檔案
- E407: 循環繼承
- E408: SSOT Quality Flags 版本不匹配
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple

import yaml

from .models import (
    ColumnAnnotation, 
    EquipmentConstraint, 
    SiteFeatureConfig,
    DeviceRole,
    PhysicalType
)

# 直接匯入 PipelineContext（annotation_manager 為 ETL Pipeline 標準元件，context 必須存在）
from ..context import PipelineContext

logger = logging.getLogger(__name__)


class FeatureAnnotationError(Exception):
    """Feature Annotation 基礎錯誤"""
    pass


class CompatibilityError(FeatureAnnotationError):
    """版本相容性錯誤 (E400)"""
    pass


class AnnotationNotFoundError(FeatureAnnotationError):
    """標註找不到錯誤 (E402)"""
    pass


class CircularInheritanceError(FeatureAnnotationError):
    """循環繼承錯誤 (E407)"""
    pass


class SSOTMismatchError(FeatureAnnotationError):
    """SSOT 版本不匹配錯誤 (E408)"""
    pass


class FeatureAnnotationManager:
    """
    特徵標註管理器
    
    使用範例:
        from src.features.annotation_manager import FeatureAnnotationManager
        from src.context import PipelineContext
        
        context = PipelineContext()
        manager = FeatureAnnotationManager("cgmh_ty", temporal_context=context)
        
        # 基礎查詢
        annotation = manager.get_column_annotation("chiller_01_chwst")
        
        # HVAC 專用查詢
        chillers = manager.get_columns_by_equipment_type("chiller")
        constraints = manager.get_equipment_constraints(phase="precheck")
    """

    def __init__(
        self, 
        site_id: str, 
        config_root: Optional[Path] = None,
        temporal_context: Optional[Any] = None
    ):
        """
        初始化 FeatureAnnotationManager
        
        Args:
            site_id: 案場識別碼
            config_root: 配置根目錄（預設為專案根目錄下的 config/features）
            temporal_context: PipelineContext 或 TemporalContext 實例
        """
        self.site_id = site_id
        
        if config_root is None:
            # 自動推導專案根目錄
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            config_root = project_root / "config" / "features"
        
        self.config_root = Path(config_root)
        self.config_path = self.config_root / "sites" / f"{site_id}.yaml"
        self.temporal_context = temporal_context
        
        # 快取
        self._cache: Optional[Dict[str, Any]] = None
        self._annotations: Dict[str, ColumnAnnotation] = {}
        self._constraints: Dict[str, EquipmentConstraint] = {}
        self._equipment_map: Dict[str, List[str]] = {}  # equipment_id -> columns
        self._metadata: Optional[Any] = None
        
        # 載入並驗證
        self._load_and_validate()
        
        logger.info(f"FeatureAnnotationManager 初始化完成: {site_id}")

    def _load_and_validate(self):
        """載入 YAML 並驗證 Schema 版本與 SSOT 一致性"""
        if not self.config_path.exists():
            raise AnnotationNotFoundError(
                f"E402: 找不到案場標註檔案: {self.config_path}\n"
                f"請確認案場 '{self.site_id}' 已建立特徵標註。"
            )

        with open(self.config_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)

        # 驗證 Schema 版本 (E400) - 支援 v1.3 與 v1.4
        schema_version = raw_data.get('metadata', {}).get('schema_version', 'unknown')
        # 標準化版本號（處理 1.4.0 → 1.4）
        version_major_minor = '.'.join(schema_version.split('.')[:2])
        if version_major_minor not in ("1.3", "1.4"):
            raise CompatibilityError(
                f"E400: 不支援的 Schema 版本: {schema_version}，預期: 1.3 或 1.4\n"
                f"請執行 migrate_excel.py 升級至 v1.3/v1.4"
            )

        # 處理繼承
        raw_data = self._resolve_inheritance(raw_data)

        # 驗證 SSOT Quality Flags 版本 (E408)
        self._validate_ssot_version(raw_data)

        # 解析 Columns
        for col_name, col_data in raw_data.get('columns', {}).items():
            self._annotations[col_name] = ColumnAnnotation(**col_data)

            # 建立 Equipment ID 映射
            eq_id = col_data.get('equipment_id')
            if eq_id:
                if eq_id not in self._equipment_map:
                    self._equipment_map[eq_id] = []
                self._equipment_map[eq_id].append(col_name)

        # 解析 Equipment Constraints
        for const_id, const_data in raw_data.get('equipment_constraints', {}).items():
            const_data['constraint_id'] = const_id
            self._constraints[const_id] = EquipmentConstraint(**const_data)

        self._cache = raw_data
        logger.debug(f"載入 {len(self._annotations)} 個欄位標註, "
                    f"{len(self._constraints)} 個設備限制")

    def _resolve_inheritance(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析繼承鏈（支援多層繼承）
        
        Args:
            raw_data: 原始 YAML 資料
            
        Returns:
            合併後的資料
            
        Raises:
            CircularInheritanceError: 偵測到循環繼承
        """
        inherit_from = raw_data.get('metadata', {}).get('inherit')
        if not inherit_from:
            return raw_data

        # 偵測循環繼承
        visited = {self.site_id}
        current = inherit_from
        
        while current:
            if current in visited:
                raise CircularInheritanceError(
                    f"E407: 循環繼承偵測到: {' -> '.join(visited)} -> {current}"
                )
            
            parent_path = self.config_root / "sites" / f"{current}.yaml"
            if not parent_path.exists():
                # 嘗試從 base.yaml 載入
                parent_path = self.config_root / f"{current}.yaml"
            
            if not parent_path.exists():
                if current == "base":
                    logger.debug("繼承來源 base 不存在，已自動忽略")
                    break
                raise AnnotationNotFoundError(
                    f"E402: 繼承來源不存在: {current}"
                )
            
            with open(parent_path, 'r', encoding='utf-8') as f:
                parent_data = yaml.safe_load(f)
            
            # 合併資料（子類覆寫父類）
            # 先合併 columns
            parent_columns = parent_data.get('columns', {})
            current_columns = raw_data.get('columns', {})
            merged_columns = {**parent_columns, **current_columns}
            raw_data['columns'] = merged_columns
            
            # 合併 equipment_constraints
            parent_constraints = parent_data.get('equipment_constraints', {})
            current_constraints = raw_data.get('equipment_constraints', {})
            merged_constraints = {**parent_constraints, **current_constraints}
            raw_data['equipment_constraints'] = merged_constraints
            
            visited.add(current)
            current = parent_data.get('metadata', {}).get('inherit')

        return raw_data

    def _validate_ssot_version(self, raw_data: Dict[str, Any]):
        """驗證 SSOT Quality Flags 版本 (E408)"""
        ssot_flags_version = raw_data.get('metadata', {}).get('ssot_flags_version')
        
        if ssot_flags_version:
            # 直接從 config_models 取得版本（VALID_QUALITY_FLAGS_VERSION 已確認定義於 v1.3.0）
            from ..etl.config_models import VALID_QUALITY_FLAGS_VERSION
            if ssot_flags_version != VALID_QUALITY_FLAGS_VERSION:
                raise SSOTMismatchError(
                    f"E408: SSOT Quality Flags 版本不匹配: "
                    f"YAML 為 {ssot_flags_version}，系統要求 {VALID_QUALITY_FLAGS_VERSION}"
                )

    # ==================== 核心查詢 API ====================

    def get_column_annotation(self, column_name: str) -> Optional[ColumnAnnotation]:
        """取得欄位完整標註"""
        return self._annotations.get(column_name)

    def is_column_annotated(self, column_name: str) -> bool:
        """檢查欄位是否已定義（E402 檢查）"""
        return column_name in self._annotations

    def get_device_role(self, column_name: str) -> Optional[str]:
        """
        取得設備角色（primary/backup/seasonal）
        
        供 Cleaner v2.2 進行語意感知清洗
        """
        anno = self._annotations.get(column_name)
        return anno.device_role.value if anno else None

    def get_equipment_id(self, column_name: str) -> Optional[str]:
        """取得設備 ID（v1.3 新增）"""
        anno = self._annotations.get(column_name)
        return anno.equipment_id if anno else None

    def get_columns_by_equipment_id(self, equipment_id: str) -> List[str]:
        """依設備 ID 取得所有相關欄位"""
        return self._equipment_map.get(equipment_id, [])

    def get_equipment_type(self, column_name: str) -> Optional[str]:
        """推導欄位的設備類型 (基於命名前綴分析)"""
        prefix_map = {
            "chiller": ["chiller_", "ch_"],
            "chw_pump": ["chw_pump_", "chwp_"],
            "cw_pump": ["cw_pump_", "cwp_"],
            "pump": ["pump_", "chw_pri_pump_", "chw_sec_pump_"],
            "cooling_tower": ["ct_", "cooling_tower_"],
            "ahu": ["ahu_"]
        }
        
        col_lower = column_name.lower()
        for eq_type, prefixes in prefix_map.items():
            if any(col_lower.startswith(p) for p in prefixes):
                return eq_type
        return None

    def get_columns_by_equipment_type(self, equipment_type: str) -> List[str]:
        """
        依設備類型取得欄位（基於命名前綴分析）

        Args:
            equipment_type: "chiller", "pump", "cooling_tower", "ahu"
        """
        prefix_map = {
            "chiller": ["chiller_", "ch_"],
            "pump": ["pump_", "chw_pri_pump_", "chw_sec_pump_", "cw_pump_", 
                    "chwp", "chws", "cwp"],
            "cooling_tower": ["ct_", "cooling_tower_"],
            "ahu": ["ahu_"]
        }

        prefixes = prefix_map.get(equipment_type, [])
        return [
            name for name in self._annotations.keys()
            if any(name.startswith(p) for p in prefixes)
        ]

    def get_target_columns(self) -> List[str]:
        """取得所有目標變數欄位（is_target=True）"""
        return [
            name for name, anno in self._annotations.items() 
            if anno.is_target
        ]

    def get_columns_by_role(self, role: str) -> List[str]:
        """
        依設備角色取得欄位清單
        
        Args:
            role: "primary", "backup", 或 "seasonal"
        """
        try:
            target_role = DeviceRole(role)
        except ValueError:
            logger.warning(f"無效的設備角色: {role}")
            return []
        
        return [
            name for name, anno in self._annotations.items()
            if anno.device_role == target_role
        ]

    def get_electrical_columns(self) -> Dict[str, List[str]]:
        """
        取得所有電力相關欄位分類
        
        Returns:
            {
                "power": ["chiller_01_kw", ...],
                "current": ["chiller_01_a", ...],
                "voltage": ["chiller_01_v", ...],
                "pf": ["chiller_01_pf", ...],
                "energy": ["chiller_01_kwh", ...]
            }
        """
        electrical_types = {
            "power": PhysicalType.POWER,
            "current": PhysicalType.CURRENT,
            "voltage": PhysicalType.VOLTAGE,
            "pf": PhysicalType.POWER_FACTOR,
            "energy": PhysicalType.ENERGY
        }
        
        return {
            key: [
                name for name, anno in self._annotations.items()
                if anno.physical_type == ptype
            ]
            for key, ptype in electrical_types.items()
        }

    def get_all_columns(self) -> List[str]:
        """取得所有欄位名稱"""
        return list(self._annotations.keys())

    def get_all_annotations(self) -> Dict[str, ColumnAnnotation]:
        """取得所有欄位標註"""
        return self._annotations.copy()

    # ==================== Equipment Validation API ====================

    def get_equipment_constraints(
        self, 
        phase: Optional[str] = None
    ) -> List[EquipmentConstraint]:
        """
        取得設備邏輯限制條件
        
        Args:
            phase: 篩選檢查階段 ("precheck" 或 "optimization")，None 則回傳全部
        
        Returns:
            EquipmentConstraint 物件列表
        """
        constraints = list(self._constraints.values())
        if phase:
            from .models import CheckPhase
            try:
                target_phase = CheckPhase(phase)
                constraints = [c for c in constraints if c.check_phase == target_phase]
            except ValueError:
                logger.warning(f"無效的檢查階段: {phase}")
        return constraints

    def get_constraints_for_column(self, column_name: str) -> List[EquipmentConstraint]:
        """
        取得適用於特定欄位的限制條件
        
        邏輯：
        - 檢查欄位是否為 trigger_status 或 required_status 的成員
        - 檢查欄位的 device_role 是否在 applicable_roles 中
        """
        anno = self._annotations.get(column_name)
        if not anno:
            return []
        
        applicable = []
        for const in self._constraints.values():
            involved = False
            if const.trigger_status and column_name in const.trigger_status:
                involved = True
            if const.required_status and column_name in const.required_status:
                involved = True
            
            if involved and anno.device_role in const.applicable_roles:
                applicable.append(const)
        
        return applicable

    def get_interlock_constraints_for_equipment(
        self, 
        equipment_id: str
    ) -> List[EquipmentConstraint]:
        """
        取得特定設備的互鎖限制（HVAC 專用）
        
        Args:
            equipment_id: 設備 ID（如 "CH-01"）
        """
        columns = self._equipment_map.get(equipment_id, [])
        constraints = []
        
        for col in columns:
            col_constraints = self.get_constraints_for_column(col)
            # 篩選互鎖類型（requires, mutex）
            interlocks = [
                c for c in col_constraints 
                if c.check_type.value in ['requires', 'mutex']
            ]
            constraints.extend(interlocks)
        
        return constraints

    # ==================== HVAC 專用查詢 ====================

    def get_chiller_columns(self, chiller_id: Optional[str] = None) -> Dict[str, List[str]]:
        """
        取得冰水主機相關欄位
        
        Args:
            chiller_id: 特定主機 ID（如 "CH-01"），None 則回傳全部
        """
        if chiller_id:
            return {chiller_id: self._equipment_map.get(chiller_id, [])}
        
        # 取得所有冰水主機欄位
        all_chiller_cols = self.get_columns_by_equipment_type("chiller")
        result = {}
        
        for col in all_chiller_cols:
            anno = self._annotations.get(col)
            if anno and anno.equipment_id:
                if anno.equipment_id not in result:
                    result[anno.equipment_id] = []
                result[anno.equipment_id].append(col)
        
        return result

    def get_efficiency_baseline(self) -> Dict[str, float]:
        """
        取得效率基準範圍（供 Cleaner 異常檢測使用）
        
        Returns:
            {"cop_min": 3.0, "cop_max": 6.0, "kw_per_rt_max": 1.2}
        """
        # 從 physical_types.yaml 讀取預設值
        physical_types_path = self.config_root / "physical_types.yaml"
        
        cop_min, cop_max = 2.0, 8.0  # 預設值
        
        if physical_types_path.exists():
            with open(physical_types_path, 'r', encoding='utf-8') as f:
                pt_data = yaml.safe_load(f)
            
            efficiency_config = pt_data.get('physical_types', {}).get('efficiency', {})
            dist_check = efficiency_config.get('distribution_check', {})
            mean_range = dist_check.get('expected_mean_range', [2.0, 8.0])
            
            if len(mean_range) >= 2:
                cop_min, cop_max = mean_range[0], mean_range[1]
        
        return {
            "cop_min": cop_min,
            "cop_max": cop_max,
            "kw_per_rt_max": 3.517 / cop_min if cop_min > 0 else 1.76
        }

    # ==================== 時間基準整合 ====================

    def get_temporal_baseline(self) -> Optional[datetime]:
        """
        取得 Pipeline 時間基準
        
        Returns:
            pipeline_origin_timestamp (datetime)
        """
        if self.temporal_context:
            if hasattr(self.temporal_context, 'get_baseline'):
                return self.temporal_context.get_baseline()
            elif hasattr(self.temporal_context, 'origin_timestamp'):
                return self.temporal_context.origin_timestamp
        return None

    def is_future_data(self, timestamp: datetime, tolerance_minutes: int = 5) -> bool:
        """
        判斷時間戳是否為未來資料
        
        Args:
            timestamp: 待檢查時間戳
            tolerance_minutes: 容許誤差（預設5分鐘）
        
        Returns:
            bool: 是否為未來資料
        """
        if not self.temporal_context:
            raise RuntimeError("E000: TemporalContext 未初始化")
        
        # 嘗試呼叫 is_future 方法
        if hasattr(self.temporal_context, 'is_future'):
            return self.temporal_context.is_future(timestamp, tolerance_minutes)
        
        # 自行計算
        from datetime import timedelta, timezone
        baseline = self.get_temporal_baseline()
        if baseline is None:
            raise RuntimeError("E000: 時間基準未建立")
        
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        threshold = baseline + timedelta(minutes=tolerance_minutes)
        return timestamp > threshold

    # ==================== 元資料查詢 ====================

    def get_metadata(self) -> Optional[Dict[str, Any]]:
        """取得文件元資料"""
        if self._cache:
            return self._cache.get('metadata')
        return None

    def get_site_id(self) -> str:
        """取得案場 ID"""
        return self.site_id

    def get_schema_version(self) -> Optional[str]:
        """取得 Schema 版本"""
        metadata = self.get_metadata()
        return metadata.get('schema_version') if metadata else None

    # ==================== 禁止寫入防護 ====================

    def __setattr__(self, name, value):
        """禁止動態修改屬性（E500 防護）"""
        if name.startswith('_') or name in [
            'site_id', 'config_root', 'config_path', 
            'temporal_context', '_cache', '_annotations', 
            '_constraints', '_equipment_map', '_metadata'
        ]:
            super().__setattr__(name, value)
        else:
            raise PermissionError(
                f"E500: FeatureAnnotationManager 為唯讀介面，"
                f"禁止修改屬性 '{name}'。請使用 Excel 編輯後重新生成 YAML。"
            )

    def save(self, *args, **kwargs):
        """明確禁止儲存操作（E501 防護）"""
        raise NotImplementedError(
            "E501: 禁止透過 FeatureAnnotationManager 儲存變更。"
            "正確流程: Excel → excel_to_yaml.py → Git Commit"
        )
