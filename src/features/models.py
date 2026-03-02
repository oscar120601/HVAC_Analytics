"""
Feature Annotation Pydantic 模型

此模組定義特徵標註的資料模型：
- ColumnAnnotation: 欄位標註
- EquipmentConstraint: 設備限制條件

驗證規則:
- E405: 目標變數禁止啟用 Lag (Target Leakage Risk)
"""

from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class DeviceRole(str, Enum):
    """設備角色列舉"""
    PRIMARY = "primary"
    BACKUP = "backup"
    SEASONAL = "seasonal"


class PhysicalType(str, Enum):
    """物理類型列舉（HVAC 擴充版）"""
    # 基礎類型
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    FLOW_RATE = "flow_rate"
    POWER = "power"
    CHILLER_LOAD = "chiller_load"
    STATUS = "status"
    GAUGE = "gauge"
    
    # HVAC 擴充類型
    COOLING_CAPACITY = "cooling_capacity"
    EFFICIENCY = "efficiency"
    ENERGY = "energy"
    VALVE_POSITION = "valve_position"
    FREQUENCY = "frequency"
    ROTATIONAL_SPEED = "rotational_speed"
    CURRENT = "current"
    VOLTAGE = "voltage"
    POWER_FACTOR = "power_factor"
    PRESSURE_DIFFERENTIAL = "pressure_differential"
    OPERATING_STATUS = "operating_status"


class ColumnStatus(str, Enum):
    """欄位狀態列舉"""
    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    DEPRECATED = "deprecated"


class ControlSemantic(str, Enum):
    """控制語意類型（v1.4 新增）"""
    ON_OFF = "on_off"
    VARIABLE_SPEED = "variable_speed"
    VALVE_POSITION = "valve_position"
    SETPOINT = "setpoint"
    FEEDBACK = "feedback"
    NONE = "none"


class NodeType(str, Enum):
    """拓樸節點類型（v1.4 新增）"""
    CHILLER = "chiller"
    PUMP = "pump"
    COOLING_TOWER = "cooling_tower"
    AHU = "ahu"
    FCU = "fcu"
    SENSOR = "sensor"
    VALVE = "valve"


class EdgeType(str, Enum):
    """拓樸邊類型（v1.4 新增）"""
    FLUID_FLOW = "fluid_flow"
    AIR_FLOW = "air_flow"
    CONTROL_SIGNAL = "control_signal"
    HEAT_TRANSFER = "heat_transfer"
    POWER = "power"


class ColumnAnnotation(BaseModel):
    """
    欄位標註資料模型（對齊 YAML Schema v1.4）
    
    Attributes:
        column_name: 欄位名稱（snake_case，必須與 CSV 標頭匹配）
        physical_type: 物理類型
        unit: 單位
        device_role: 設備角色（primary/backup/seasonal）
        equipment_id: 設備 ID（v1.3 新增）
        description: 描述
        is_target: 是否為目標變數
        enable_lag: 是否啟用 Lag 特徵
        lag_intervals: Lag 間隔列表（時間點間隔）
        ignore_warnings: 忽略的警告代碼列表
        status: 欄位狀態
        control_semantic: 控制語意類型（v1.4 新增）
        topology_node_id: 對應拓樸節點 ID（v1.4 新增）
        decay_factor: Hop-N 衰減係數（v1.4 新增）
    """
    
    column_name: str = Field(..., description="欄位名稱（snake_case）")
    physical_type: PhysicalType = Field(..., description="物理類型")
    unit: Optional[str] = Field(None, description="單位")
    device_role: DeviceRole = Field(default=DeviceRole.PRIMARY, description="設備角色")
    equipment_id: Optional[str] = Field(None, description="設備 ID（如 CH-01）")
    description: Optional[str] = Field(None, description="欄位描述")
    is_target: bool = Field(default=False, description="是否為目標變數")
    enable_lag: bool = Field(default=True, description="是否啟用 Lag")
    lag_intervals: List[int] = Field(default_factory=list, description="Lag 間隔列表")
    ignore_warnings: List[str] = Field(default_factory=list, description="忽略的警告代碼")
    status: ColumnStatus = Field(default=ColumnStatus.PENDING_REVIEW, description="欄位狀態")
    control_semantic: ControlSemantic = Field(default=ControlSemantic.NONE, description="控制語意類型（v1.4）")
    topology_node_id: Optional[str] = Field(None, description="拓樸節點 ID（v1.4）")
    decay_factor: Optional[float] = Field(None, description="衰減係數（v1.4）", ge=0, le=1)
    
    @field_validator('column_name')
    @classmethod
    def validate_column_name(cls, v: str) -> str:
        """驗證欄位名稱格式（暫時放寬，以支援自動產生的原始標頭）"""
        return v
    
    @field_validator('lag_intervals')
    @classmethod
    def validate_lag_intervals(cls, v: List[int]) -> List[int]:
        """驗證 Lag 間隔為嚴格遞增的正整數序列"""
        if not v:
            return v
        
        # 檢查是否為正整數
        if not all(isinstance(x, int) and x > 0 for x in v):
            raise ValueError("Lag 間隔必須為正整數")
        
        # 檢查是否嚴格遞增
        if v != sorted(set(v)):
            raise ValueError("Lag 間隔必須為嚴格遞增序列，且不可重複")
        
        return v
    
    @model_validator(mode='after')
    def check_target_lag(self) -> 'ColumnAnnotation':
        """
        E405: 目標變數禁止啟用 Lag（Target Leakage Risk）
        """
        if self.is_target and self.enable_lag:
            raise ValueError(
                f"E405: 目標變數 '{self.column_name}' 不可啟用 Lag，"
                "這會導致資料洩漏（Data Leakage）"
            )
        return self


class ConstraintType(str, Enum):
    """限制條件類型"""
    REQUIRES = "requires"           # 需要條件
    MUTEX = "mutex"                 # 互斥條件
    SEQUENCE = "sequence"           # 順序條件
    RANGE_CHECK = "range_check"     # 範圍檢查
    THRESHOLD = "threshold"         # 閾值檢查


class CheckPhase(str, Enum):
    """檢查階段"""
    PRECHECK = "precheck"           # Cleaner 階段
    OPTIMIZATION = "optimization"   # Optimization 階段


class Severity(str, Enum):
    """嚴重程度"""
    CRITICAL = "critical"
    WARNING = "warning"


class EquipmentConstraint(BaseModel):
    """
    設備限制條件模型（對齊 Interface Contract v1.1）
    
    Attributes:
        constraint_id: 限制條件 ID
        description: 描述
        check_type: 檢查類型
        check_phase: 檢查階段
        trigger_status: 觸發條件欄位列表
        required_status: 需求條件欄位列表
        target_column: 目標欄位
        min_value: 最小值
        max_value: 最大值
        min_duration_minutes: 最小持續時間（分鐘）
        severity: 嚴重程度
        applicable_roles: 適用的設備角色
        error_code: 錯誤代碼
    """
    
    constraint_id: str = Field(..., description="限制條件 ID")
    description: str = Field(..., description="描述")
    check_type: ConstraintType = Field(..., description="檢查類型")
    check_phase: CheckPhase = Field(..., description="檢查階段")
    trigger_status: Optional[List[str]] = Field(None, description="觸發條件欄位")
    required_status: Optional[List[str]] = Field(None, description="需求條件欄位")
    target_column: Optional[str] = Field(None, description="目標欄位")
    min_value: Optional[float] = Field(None, description="最小值")
    max_value: Optional[float] = Field(None, description="最大值")
    min_duration_minutes: Optional[int] = Field(None, description="最小持續時間（分鐘）")
    severity: Severity = Field(default=Severity.CRITICAL, description="嚴重程度")
    applicable_roles: List[DeviceRole] = Field(
        default=[DeviceRole.PRIMARY, DeviceRole.BACKUP],
        description="適用的設備角色"
    )
    error_code: Optional[str] = Field(None, description="錯誤代碼")
    
    @model_validator(mode='after')
    def validate_constraint_logic(self) -> 'EquipmentConstraint':
        """驗證限制條件邏輯一致性"""
        
        if self.check_type == ConstraintType.REQUIRES:
            if not self.trigger_status or not self.required_status:
                raise ValueError(
                    f"REQUIRES 類型必須指定 trigger_status 和 required_status"
                )
        
        elif self.check_type == ConstraintType.MUTEX:
            # mutex_pairs 在實際使用時解析
            pass
        
        elif self.check_type in [ConstraintType.RANGE_CHECK, ConstraintType.THRESHOLD]:
            if not self.target_column:
                raise ValueError(
                    f"{self.check_type} 類型必須指定 target_column"
                )
        
        return self


class FeatureMetadata(BaseModel):
    """
    Feature Annotation 文件元資料
    
    對應 Excel Sheet 3: Metadata
    """
    schema_version: str = Field(default="1.3", description="Schema 版本")
    template_version: str = Field(default="1.3", description="範本版本")
    site_id: str = Field(..., description="案場識別碼")
    inherit: Optional[str] = Field(None, description="繼承來源")
    description: Optional[str] = Field(None, description="文件描述")
    editor: str = Field(..., description="編輯者")
    last_updated: str = Field(..., description="最後更新時間（ISO 8601）")
    yaml_checksum: Optional[str] = Field(None, description="對應 YAML 雜湊")
    equipment_schema: str = Field(default="hvac_v1.3", description="設備分類架構版本")
    temporal_baseline_version: str = Field(default="1.0", description="時間基準版本")
    ssot_flags_version: Optional[str] = Field(None, description="SSOT Quality Flags 版本")


class TopologyNode(BaseModel):
    """
    拓樸節點定義（v1.4 新增）
    
    Attributes:
        node_id: 節點唯一識別碼
        node_type: 節點類型
        equipment_id: 對應設備 ID
        features: 節點特徵欄位列表
        control_semantic: 控制語意類型
    """
    node_id: str = Field(..., description="節點 ID")
    node_type: NodeType = Field(..., description="節點類型")
    equipment_id: str = Field(..., description="設備 ID")
    features: List[str] = Field(default_factory=list, description="節點特徵欄位")
    control_semantic: ControlSemantic = Field(default=ControlSemantic.NONE, description="控制語意")


class TopologyEdge(BaseModel):
    """
    拓樸邊定義（v1.4 新增）
    
    Attributes:
        source: 源節點 ID
        target: 目標節點 ID
        edge_type: 邊類型
        weight: 邊權重
    """
    source: str = Field(..., description="源節點 ID")
    target: str = Field(..., description="目標節點 ID")
    edge_type: EdgeType = Field(..., description="邊類型")
    weight: float = Field(default=1.0, description="邊權重")


class TopologyConfig(BaseModel):
    """
    GNN 拓樸配置（v1.4 新增）
    
    Attributes:
        nodes: 設備節點列表
        edges: 連接邊列表
        decay_factors: Hop-N 衰減係數設定
    """
    nodes: List[TopologyNode] = Field(default_factory=list, description="節點列表")
    edges: List[TopologyEdge] = Field(default_factory=list, description="邊列表")
    decay_factors: Dict[str, float] = Field(
        default_factory=dict,
        description="Hop-N 衰減係數"
    )


class SiteFeatureConfig(BaseModel):
    """
    案場特徵配置（完整 YAML 結構 v1.4）
    
    對應 YAML 檔案格式
    """
    metadata: FeatureMetadata
    columns: Dict[str, ColumnAnnotation]
    equipment_constraints: Optional[Dict[str, EquipmentConstraint]] = Field(
        default_factory=dict,
        description="設備限制條件"
    )
    topology: Optional[TopologyConfig] = Field(
        default=None,
        description="GNN 拓樸定義（v1.4）"
    )
    
    @model_validator(mode='after')
    def sync_column_names(self) -> 'SiteFeatureConfig':
        """確保 ColumnAnnotation 的 column_name 與 dict key 一致"""
        for key, annotation in self.columns.items():
            if annotation.column_name != key:
                annotation.column_name = key
        return self
