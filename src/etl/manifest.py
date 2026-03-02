"""
Manifest 模型定義 (v1.3-Contract-Aligned)

此模組定義 BatchProcessor 輸出的 Manifest 結構，包含：
- Temporal Baseline 傳遞
- Feature Metadata (不含 device_role)
- Annotation 稽核軌跡
- Equipment Validation Audit
- SSOT 版本快照

對應 PRD: PRD_BATCH_PROCESSOR_v1.3.md
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

from pydantic import BaseModel, Field, validator


class FeatureMetadata(BaseModel):
    """欄位元資料 (僅含物理屬性，不含 device_role)"""
    physical_type: str = Field(default="gauge", description="物理類型")
    unit: Optional[str] = Field(default=None, description="單位")
    description: Optional[str] = Field(default=None, description="欄位描述")
    column_name: Optional[str] = Field(default=None, description="原始欄位名稱")
    # 🆕 v1.4: GNN 拓樸欄位
    topology_node_id: Optional[str] = Field(default=None, description="GNN 節點 ID")
    control_semantic: Optional[str] = Field(default=None, description="控制語意")
    decay_factor: Optional[float] = Field(default=None, description="衰減係數")
    
    class Config:
        extra = "forbid"  # 禁止額外欄位，防止 device_role 洩漏


class TemporalBaseline(BaseModel):
    """時間基準資訊"""
    pipeline_origin_timestamp: str = Field(..., description="ISO 8601 UTC 時間戳")
    timezone: str = Field(default="UTC", description="時區")
    baseline_version: str = Field(default="1.0", description="時間基準版本")


class AnnotationAuditTrail(BaseModel):
    """Annotation 稽核軌跡"""
    schema_version: str = Field(default="unknown", description="Schema 版本")
    template_version: str = Field(default="unknown", description="範本版本")
    yaml_checksum: str = Field(default="", description="YAML 檔案雜湊")
    inheritance_chain: str = Field(default="none", description="繼承鏈資訊")
    last_updated: str = Field(default="", description="最後更新時間")
    editor: str = Field(default="unknown", description="編輯者")


class EquipmentValidationAudit(BaseModel):
    """設備驗證稽核軌跡"""
    validation_enabled: bool = Field(default=False, description="是否啟用驗證")
    constraints_applied: List[str] = Field(default_factory=list, description="套用的限制條件 ID")
    violations_detected: int = Field(default=0, description="違規筆數")
    violation_details: List[Dict[str, Any]] = Field(default_factory=list, description="違規詳情")
    precheck_timestamp: str = Field(default="", description="預檢執行時間戳")
    audit_generated_at: Optional[str] = Field(default=None, description="稽核軌跡產生時間")


class TopologyNode(BaseModel):
    """🆕 v1.4: GNN 拓樸節點定義"""
    node_id: str = Field(..., description="節點唯一識別碼")
    node_type: str = Field(default="equipment", description="節點類型 (equipment, sensor, control)")
    equipment_id: Optional[str] = Field(default=None, description="關聯設備 ID")
    features: List[str] = Field(default_factory=list, description="關聯的特徵欄位名稱列表")


class TopologyEdge(BaseModel):
    """🆕 v1.4: GNN 拓樸邊緣定義"""
    source: str = Field(..., description="源節點 ID")
    target: str = Field(..., description="目標節點 ID")
    edge_type: str = Field(default="fluid", description="邊緣類型 (fluid, control_signal, heat_transfer)")
    weight: Optional[float] = Field(default=None, description="邊緣權重")


class TopologyContext(BaseModel):
    """🆕 v1.4: GNN 完整拓樸上下文"""
    nodes: List[TopologyNode] = Field(default_factory=list, description="節點列表")
    edges: List[TopologyEdge] = Field(default_factory=list, description="邊緣列表")
    adjacency_matrix_path: Optional[str] = Field(default=None, description="Parquet 中鄰接矩陣的儲存路徑")
    decay_factors: Dict[str, float] = Field(default_factory=dict, description="節點 ID → 衰減係數映射")


class TimestampSchema(BaseModel):
    """時間戳規格"""
    format: str = Field(default="INT64", description="物理格式")
    unit: str = Field(default="nanoseconds", description="時間單位")
    timezone: str = Field(default="UTC", description="時區")


class ManifestStatistics(BaseModel):
    """批次統計資訊"""
    total_rows: int = Field(default=0, description="總列數")
    total_cols: int = Field(default=0, description="總欄位數")
    time_range: Dict[str, str] = Field(default_factory=dict, description="時間範圍")
    null_percent: float = Field(default=0.0, description="空值百分比")
    files_count: int = Field(default=0, description="檔案數量")


class Manifest(BaseModel):
    """
    BatchProcessor v1.3-Contract-Aligned Manifest
    
    用於傳遞批次處理結果至下游 Feature Engineer
    """
    
    # 基礎資訊
    manifest_version: str = Field(default="1.3-CA", description="Manifest 版本")
    batch_id: str = Field(..., description="批次 UUID")
    site_id: str = Field(..., description="案場 ID")
    created_at: datetime = Field(..., description="建立時間 (UTC)")
    
    # 【關鍵】時間基準傳遞
    temporal_baseline: TemporalBaseline = Field(..., description="時間基準")
    
    # Feature Metadata (僅含物理屬性)
    feature_metadata: Dict[str, FeatureMetadata] = Field(
        default_factory=dict, 
        description="欄位元資料 (不含 device_role)"
    )
    
    # 【新增】稽核軌跡
    annotation_audit_trail: AnnotationAuditTrail = Field(
        default_factory=AnnotationAuditTrail,
        description="Annotation 稽核軌跡"
    )
    
    # 【新增】設備驗證稽核
    equipment_validation_audit: EquipmentValidationAudit = Field(
        default_factory=EquipmentValidationAudit,
        description="設備驗證稽核軌跡"
    )
    
    # 🆕 v1.4: GNN 拓樸上下文
    topology_context: Optional[TopologyContext] = Field(
        default=None,
        description="GNN 拓樸上下文（節點、邊緣、鄰接矩陣）"
    )
    
    # SSOT 版本快照
    quality_flags_schema: List[str] = Field(
        default_factory=list,
        description="VALID_QUALITY_FLAGS 快照 (供 E408 檢查)"
    )
    timestamp_schema: TimestampSchema = Field(
        default_factory=TimestampSchema,
        description="時間戳規格"
    )
    
    # 輸出檔案資訊
    output_files: List[str] = Field(default_factory=list, description="輸出檔案列表")
    output_format: str = Field(default="parquet", description="輸出格式")
    compression: str = Field(default="snappy", description="壓縮方式")
    
    # 統計資訊
    statistics: ManifestStatistics = Field(
        default_factory=ManifestStatistics,
        description="批次統計"
    )
    
    # 完整性驗證
    checksum: Optional[str] = Field(default=None, description="Manifest 雜湊")
    file_checksums: Dict[str, str] = Field(
        default_factory=dict,
        description="檔案名稱 → SHA256 雜湊"
    )
    
    @validator('feature_metadata')
    def validate_no_device_role(cls, v: Dict[str, FeatureMetadata]) -> Dict[str, FeatureMetadata]:
        """驗證 feature_metadata 不含 device_role"""
        for col_name, meta in v.items():
            if hasattr(meta, 'device_role') or 'device_role' in meta.dict():
                raise ValueError(
                    f"E500: feature_metadata 包含 device_role。 "
                    f"Cleaner 不應傳遞 device_role 至 BatchProcessor。"
                )
        return v
    
    def compute_checksum(self) -> str:
        """計算 Manifest 內容雜湊 (排除 checksum 欄位本身)"""
        # 建立可序列化的字典副本
        data = self.dict(exclude={'checksum'})
        # 將 datetime 轉為 ISO 格式字串以確保一致性
        data['created_at'] = data['created_at'].isoformat() if data.get('created_at') else None
        # 計算 SHA256
        content = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def validate_checksum(self) -> bool:
        """驗證 Manifest 完整性"""
        if not self.checksum:
            return False
        return self.compute_checksum() == self.checksum
    
    def write_to_file(self, path: Path) -> None:
        """將 Manifest 寫入檔案"""
        # 更新 checksum
        self.checksum = self.compute_checksum()
        
        # 相容 Pydantic v1 與 v2
        try:
            data = self.model_dump(mode='json')
        except AttributeError:
            data = json.loads(self.json())
            
        content = json.dumps(data, indent=2, ensure_ascii=False)
        path.write_text(content, encoding='utf-8')
    
    @classmethod
    def read_from_file(cls, path: Path) -> "Manifest":
        """從檔案讀取 Manifest"""
        data = json.loads(path.read_text(encoding='utf-8'))
        return cls.parse_obj(data)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# =============================================================================
# 輔助函數
# =============================================================================

def create_default_manifest(
    batch_id: str,
    site_id: str,
    pipeline_origin_timestamp: datetime
) -> Manifest:
    """
    建立預設 Manifest
    
    Args:
        batch_id: 批次 ID
        site_id: 案場 ID
        pipeline_origin_timestamp: Pipeline 啟動時間戳
    
    Returns:
        Manifest 實例
    """
    return Manifest(
        batch_id=batch_id,
        site_id=site_id,
        created_at=datetime.now(timezone.utc),
        temporal_baseline=TemporalBaseline(
            pipeline_origin_timestamp=pipeline_origin_timestamp.isoformat(),
            timezone="UTC",
            baseline_version="1.0"
        )
    )
