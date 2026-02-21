"""
HVAC-1 Feature Annotation 模組

此模組提供特徵標註管理功能，包含：
- FeatureAnnotationManager: 唯讀特徵標註查詢
- ColumnAnnotation: 欄位標註資料模型
- EquipmentConstraint: 設備限制條件模型

設計原則:
- 唯讀介面：提供查詢方法，禁止修改 YAML
- SSOT 存取：所有資料來自 config/features/sites/{site_id}.yaml
- 快取機制：YAML 載入後快取於記憶體，避免重複 I/O

錯誤代碼:
- E400-E409: Feature Annotation 錯誤
- E500-E501: Governance 錯誤
"""

from .models import ColumnAnnotation, EquipmentConstraint
from .annotation_manager import FeatureAnnotationManager

__all__ = [
    "ColumnAnnotation",
    "EquipmentConstraint", 
    "FeatureAnnotationManager",
]

__version__ = "1.3.0"
