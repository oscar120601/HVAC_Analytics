"""
HVAC-1 Feature Annotation 模組 v1.4

此模組提供特徵標註管理功能，包含：
- FeatureAnnotationManager: 唯讀特徵標註查詢
- TopologyManager: 設備拓樸圖管理
- ControlSemanticsManager: 控制語意管理
- ColumnAnnotation: 欄位標註資料模型
- EquipmentConstraint: 設備限制條件模型

設計原則:
- 唯讀介面：提供查詢方法，禁止修改 YAML
- SSOT 存取：所有資料來自 config/features/sites/{site_id}.yaml
- 快取機制：YAML 載入後快取於記憶體，避免重複 I/O

錯誤代碼:
- E400-E409: Feature Annotation 錯誤
- E411: 拓樸圖無效
- E413: Topology 版本不符
- E420: Control Semantics 版本不符
- E421: Control Pair 不完整
- E500-E501: Governance 錯誤
"""

from .models import ColumnAnnotation, EquipmentConstraint
from .annotation_manager import FeatureAnnotationManager
from .topology_manager import TopologyManager
from .control_semantics_manager import ControlSemanticsManager

__all__ = [
    "ColumnAnnotation",
    "EquipmentConstraint",
    "FeatureAnnotationManager",
    "TopologyManager",
    "ControlSemanticsManager",
]

__version__ = "1.4.0"
