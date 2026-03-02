"""
HVAC-1 系統配置模型與 SSOT (Single Source of Truth) 定義

此模組為全系統的單一真相源，包含：
- 錯誤代碼常數 (E000-E999)
- 品質標記定義 (VALID_QUALITY_FLAGS)
- 時間戳規格 (TIMESTAMP_CONFIG)
- Feature Annotation 常數
- Header 正規化規則
- 設備驗證限制條件

設計原則:
- 所有模組必須引用此檔案的常數，禁止硬編碼
- 任何變更必須通過版本控制並通知所有下游模組
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import threading
import re


# =============================================================================
# 1. 錯誤代碼分層定義 (Error Code Hierarchy E000-E999)
# =============================================================================

class ErrorSeverity(Enum):
    """錯誤嚴重度等級"""
    CRITICAL = "critical"      # 必須終止流程
    HIGH = "high"              # 高風險，通常終止
    MEDIUM = "medium"          # 中等風險，可恢復
    WARNING = "warning"        # 警告，繼續執行
    INFO = "info"              # 資訊性


@dataclass
class ErrorCode:
    """錯誤代碼定義"""
    code: str
    name: str
    module: str
    description: str
    severity: ErrorSeverity
    user_message_template: str
    recoverable: bool


# E000: 全域時間基準錯誤
E000_TEMPORAL_BASELINE_MISSING = ErrorCode(
    code="E000",
    name="TEMPORAL_BASELINE_MISSING",
    module="Container/任意",
    description="pipeline_origin_timestamp 未傳遞或遺失",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="時間基準遺失: 無法執行時間相關驗證",
    recoverable=False
)

E000W_TEMPORAL_DRIFT_WARNING = ErrorCode(
    code="E000-W",
    name="TEMPORAL_DRIFT_WARNING",
    module="PipelineContext",
    description="流程執行時間超過 1 小時，懷疑時間漂移",
    severity=ErrorSeverity.WARNING,
    user_message_template="警告: Pipeline 執行時間過長，請檢查時間基準",
    recoverable=True
)

# E001-E099: 系統層級錯誤
E001_ENCODING_MISMATCH = ErrorCode(
    code="E001",
    name="ENCODING_MISMATCH",
    module="Parser",
    description="檔案編碼無法偵測或輸出含非法字元 (BOM)",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="檔案編碼錯誤: 無法識別編碼或包含 BOM 殘留",
    recoverable=False
)

E006_MEMORY_LIMIT_EXCEEDED = ErrorCode(
    code="E006",
    name="MEMORY_LIMIT_EXCEEDED",
    module="任意",
    description="記憶體使用超過配置上限",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="記憶體不足: 已超過 {limit}GB 上限",
    recoverable=False
)

E007_CONFIG_FILE_CORRUPTED = ErrorCode(
    code="E007",
    name="CONFIG_FILE_CORRUPTED",
    module="ConfigLoader",
    description="YAML/JSON 設定檔解析失敗",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="設定檔損毀: {filepath}",
    recoverable=False
)

# E100-E199: Parser 錯誤
E101_ENCODING_MISMATCH = ErrorCode(
    code="E101",
    name="ENCODING_MISMATCH",
    module="Parser",
    description="無法偵測檔案編碼或含BOM",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="編碼錯誤: 無法偵測檔案編碼或包含BOM殘留",
    recoverable=False
)

E102_TIMEZONE_VIOLATION = ErrorCode(
    code="E102",
    name="TIMEZONE_VIOLATION",
    module="Parser",
    description="時區非 UTC 或精度錯誤",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="時區違反: 時間戳必須為 UTC 時區",
    recoverable=False
)

E103_CONTRACT_VIOLATION = ErrorCode(
    code="E103",
    name="CONTRACT_VIOLATION",
    module="Parser",
    description="缺少必要欄位或 Quality Flags 未定義",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="契約違反: 缺少必要欄位或品質標記未定義",
    recoverable=False
)

E104_HEADER_NOT_FOUND = ErrorCode(
    code="E104",
    name="HEADER_NOT_FOUND",
    module="Parser",
    description="無法定位標頭行 (掃描 > 500行)",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="標頭未找到: 掃描超過500行仍無法定位標頭",
    recoverable=False
)

E105_HEADER_STANDARDIZATION_FAILED = ErrorCode(
    code="E105",
    name="HEADER_STANDARDIZATION_FAILED",
    module="Parser",
    description="標頭正規化失敗（不符合命名規則或 Regex 匹配失敗）",
    severity=ErrorSeverity.HIGH,
    user_message_template="標頭正規化失敗: '{header}' 無法轉換為有效識別符",
    recoverable=False
)

E111_TIMEZONE_WARNING = ErrorCode(
    code="E111",
    name="TIMEZONE_WARNING",
    module="Parser",
    description="時區轉換警告 (非致命)",
    severity=ErrorSeverity.WARNING,
    user_message_template="時區警告: 已自動轉換時區至 UTC",
    recoverable=True
)

E112_FUTURE_DATA_DETECTED = ErrorCode(
    code="E112",
    name="FUTURE_DATA_DETECTED",
    module="Parser",
    description="發現未來資料 (相對於 pipeline_timestamp)",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="未來資料偵測: 資料時間超過允許範圍",
    recoverable=False
)

# E200-E299: Cleaner/BatchProcessor 錯誤
E201_INPUT_SCHEMA_MISMATCH = ErrorCode(
    code="E201",
    name="INPUT_SCHEMA_MISMATCH",
    module="BatchProcessor",
    description="輸入 DataFrame Schema 不符",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="輸入資料格式不符: {detail}",
    recoverable=False
)

E202_UNKNOWN_QUALITY_FLAG = ErrorCode(
    code="E202",
    name="UNKNOWN_QUALITY_FLAG",
    module="BatchProcessor",
    description="輸入含未定義的品質標記",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="品質標記未定義於 SSOT: {flags}",
    recoverable=False
)

E203_METADATA_LOSS = ErrorCode(
    code="E203",
    name="METADATA_LOSS",
    module="BatchProcessor",
    description="未接收到 column_metadata",
    severity=ErrorSeverity.WARNING,
    user_message_template="缺少欄位元資料，使用保守預設",
    recoverable=True
)

E205_FUTURE_DATA_IN_BATCH = ErrorCode(
    code="E205",
    name="FUTURE_DATA_IN_BATCH",
    module="BatchProcessor",
    description="批次資料包含超過 pipeline_origin_timestamp + 5min 的時間戳",
    severity=ErrorSeverity.HIGH,
    user_message_template="批次含未來資料，已拒絕",
    recoverable=False
)

E206_PARQUET_FORMAT_VIOLATION = ErrorCode(
    code="E206",
    name="PARQUET_FORMAT_VIOLATION",
    module="BatchProcessor",
    description="Parquet 格式非 INT64/UTC",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="Parquet 格式錯誤: {detail}",
    recoverable=False
)

# E210-E299: Cleaner 階段
E210_PHYSICAL_CONSTRAINT_VIOLATION = ErrorCode(
    code="E210",
    name="PHYSICAL_CONSTRAINT_VIOLATION",
    module="Cleaner",
    description="資料違反物理限制（如溫度 > 100°C）",
    severity=ErrorSeverity.HIGH,
    user_message_template="物理限制違反: 資料超出合理物理範圍",
    recoverable=True
)

E211_FROZEN_DATA_DETECTED = ErrorCode(
    code="E211",
    name="FROZEN_DATA_DETECTED",
    module="Cleaner",
    description="連續多筆相同值（設備可能卡死）",
    severity=ErrorSeverity.WARNING,
    user_message_template="凍結資料偵測: 連續多筆相同值，設備可能卡死",
    recoverable=True
)

E212_ZERO_RATIO_EXCEEDED = ErrorCode(
    code="E212",
    name="ZERO_RATIO_EXCEEDED",
    module="Cleaner",
    description="零值比例過高（主設備異常）",
    severity=ErrorSeverity.HIGH,
    user_message_template="零值比例過高: 主設備可能異常",
    recoverable=True
)

E213_INSUFFICIENT_DATA_GAP = ErrorCode(
    code="E213",
    name="INSUFFICIENT_DATA_GAP",
    module="Cleaner",
    description="時間軸缺漏過大（> 1小時）",
    severity=ErrorSeverity.HIGH,
    user_message_template="資料缺漏過大: 時間軸缺漏超過1小時",
    recoverable=True
)

# E300-E349: Feature Engineer 輸入錯誤
E301_MANIFEST_INTEGRITY_FAILED = ErrorCode(
    code="E301",
    name="MANIFEST_INTEGRITY_FAILED",
    module="FeatureEngineer",
    description="Manifest 損毀或 checksum 驗證失敗",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="Manifest 完整性驗證失敗: {filepath}",
    recoverable=False
)

E302_SCHEMA_MISMATCH = ErrorCode(
    code="E302",
    name="SCHEMA_MISMATCH",
    module="FeatureEngineer",
    description="timestamp 格式不符 (INT64/nanoseconds/UTC)",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="Schema 不符: timestamp 必須為 INT64/nanoseconds/UTC",
    recoverable=False
)

E303_UNKNOWN_QUALITY_FLAG = ErrorCode(
    code="E303",
    name="UNKNOWN_QUALITY_FLAG",
    module="FeatureEngineer",
    description="輸入包含未定義的 quality_flags",
    severity=ErrorSeverity.HIGH,
    user_message_template="未知的品質標記: {flags}",
    recoverable=True
)

E304_METADATA_MISSING = ErrorCode(
    code="E304",
    name="METADATA_MISSING",
    module="FeatureEngineer",
    description="缺少 feature_metadata",
    severity=ErrorSeverity.WARNING,
    user_message_template="缺少欄位元資料，使用保守預設",
    recoverable=True
)

E305_DATA_LEAKAGE_DETECTED = ErrorCode(
    code="E305",
    name="DATA_LEAKAGE_DETECTED",
    module="FeatureEngineer",
    description="偵測到 Data Leakage (目標變數資訊洩漏至特徵)",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="Data Leakage 偵測: {detail}",
    recoverable=False
)

E306_DYNAMIC_GLOBAL_MEAN_RISK = ErrorCode(
    code="E306",
    name="DYNAMIC_GLOBAL_MEAN_RISK",
    module="FeatureEngineer",
    description="嚴格模式下禁止動態計算全域平均值 (Data Leakage 風險)",
    severity=ErrorSeverity.HIGH,
    user_message_template="Data Leakage 風險: 必須提供 Model Artifact 中的 scaling_stats",
    recoverable=False
)

# E350-E399: Equipment Validation 錯誤
E350_EQUIPMENT_LOGIC_PRECHECK_FAILED = ErrorCode(
    code="E350",
    name="EQUIPMENT_LOGIC_PRECHECK_FAILED",
    module="Cleaner",
    description="基礎設備邏輯預檢失敗（如主機開但水泵關）",
    severity=ErrorSeverity.HIGH,
    user_message_template="設備邏輯預檢失敗: 基礎設備邏輯違規",
    recoverable=True
)

E351_EQUIPMENT_VALIDATION_AUDIT_MISSING = ErrorCode(
    code="E351",
    name="EQUIPMENT_VALIDATION_AUDIT_MISSING",
    module="BatchProcessor",
    description="啟用同步但未記錄稽核軌跡",
    severity=ErrorSeverity.WARNING,
    user_message_template="設備驗證稽核軌跡遺失",
    recoverable=False
)

E352_EQUIPMENT_CONSTRAINT_MISMATCH = ErrorCode(
    code="E352",
    name="EQUIPMENT_CONSTRAINT_MISMATCH",
    module="FeatureEngineer",
    description="特徵工程與設備限制邏輯不一致",
    severity=ErrorSeverity.HIGH,
    user_message_template="設備限制不一致",
    recoverable=False
)

E353_REQUIRES_VIOLATION = ErrorCode(
    code="E353",
    name="REQUIRES_VIOLATION",
    module="EquipmentValidator",
    description="違反「必須同時開啟」約束",
    severity=ErrorSeverity.HIGH,
    user_message_template="違反必須同時開啟約束",
    recoverable=True
)

E354_MUTEX_VIOLATION = ErrorCode(
    code="E354",
    name="MUTEX_VIOLATION",
    module="EquipmentValidator",
    description="違反「互斥」約束",
    severity=ErrorSeverity.HIGH,
    user_message_template="違反互斥約束",
    recoverable=True
)

E355_SEQUENCE_VIOLATION = ErrorCode(
    code="E355",
    name="SEQUENCE_VIOLATION",
    module="EquipmentValidator",
    description="違反開關機順序約束",
    severity=ErrorSeverity.HIGH,
    user_message_template="違反開關機順序約束",
    recoverable=True
)

E356_MIN_RUNTIME_VIOLATION = ErrorCode(
    code="E356",
    name="MIN_RUNTIME_VIOLATION",
    module="EquipmentValidator",
    description="違反最小運轉時間限制",
    severity=ErrorSeverity.HIGH,
    user_message_template="違反最小運轉時間限制",
    recoverable=True
)

E357_MIN_DOWNTIME_VIOLATION = ErrorCode(
    code="E357",
    name="MIN_DOWNTIME_VIOLATION",
    module="EquipmentValidator",
    description="違反最小停機時間限制",
    severity=ErrorSeverity.HIGH,
    user_message_template="違反最小停機時間限制",
    recoverable=True
)

# E400-E499: Feature Annotation 錯誤
E400_ANNOTATION_VERSION_MISMATCH = ErrorCode(
    code="E400",
    name="ANNOTATION_VERSION_MISMATCH",
    module="ConfigLoader/FE",
    description="Schema 版本不符或範本過舊",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="Feature Annotation 版本過舊: 請執行 migrate-excel",
    recoverable=False
)

E401_ORPHAN_COLUMN = ErrorCode(
    code="E401",
    name="ORPHAN_COLUMN",
    module="excel_to_yaml",
    description="標註欄位不存在於資料",
    severity=ErrorSeverity.WARNING,
    user_message_template="標註欄位 {col} 不存在於 CSV",
    recoverable=True
)

E402_UNANNOTATED_COLUMN = ErrorCode(
    code="E402",
    name="UNANNOTATED_COLUMN",
    module="ConfigLoader/Cleaner",
    description="資料欄位未定義於 Annotation",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="未定義欄位: {col}，請執行 features wizard",
    recoverable=False
)

E403_UNIT_INCOMPATIBLE = ErrorCode(
    code="E403",
    name="UNIT_INCOMPATIBLE",
    module="excel_to_yaml",
    description="單位與物理類型不匹配",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="單位錯誤: {unit} 不適用於 {physical_type}",
    recoverable=False
)

E404_LAG_FORMAT_INVALID = ErrorCode(
    code="E404",
    name="LAG_FORMAT_INVALID",
    module="excel_to_yaml",
    description="Lag 間隔格式錯誤",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="Lag 格式錯誤: 必須為逗號分隔整數",
    recoverable=False
)

E405_TARGET_LEAKAGE_RISK = ErrorCode(
    code="E405",
    name="TARGET_LEAKAGE_RISK",
    module="Pydantic Validation",
    description="is_target=True 但 enable_lag=True",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="目標變數不可啟用 Lag",
    recoverable=False
)

E406_EXCEL_YAML_OUT_OF_SYNC = ErrorCode(
    code="E406",
    name="EXCEL_YAML_OUT_OF_SYNC",
    module="ConfigLoader",
    description="Excel 與 YAML 不同步",
    severity=ErrorSeverity.HIGH,
    user_message_template="設定不同步: 請執行 validate-annotation",
    recoverable=False
)

E407_CIRCULAR_INHERITANCE = ErrorCode(
    code="E407",
    name="CIRCULAR_INHERITANCE",
    module="AnnotationManager",
    description="YAML 繼承循環",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="繼承循環偵測: {chain}",
    recoverable=False
)

E408_SSOT_QUALITY_FLAGS_MISMATCH = ErrorCode(
    code="E408",
    name="SSOT_QUALITY_FLAGS_MISMATCH",
    module="Container",
    description="YAML 中的 flags 與 VALID_QUALITY_FLAGS 不一致",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="SSOT 品質標記不匹配: 請同步 config_models.py",
    recoverable=False
)

E409_HEADER_ANNOTATION_MISMATCH = ErrorCode(
    code="E409",
    name="HEADER_ANNOTATION_MISMATCH",
    module="Parser/AnnotationManager",
    description="CSV 標頭（正規化後）與 Annotation 欄位名稱不匹配",
    severity=ErrorSeverity.HIGH,
    user_message_template="CSV 標頭 {header} 無法對應至 Annotation",
    recoverable=False
)

# E500-E599: Governance & Architecture Violations
E500_DEVICE_ROLE_LEAKAGE = ErrorCode(
    code="E500",
    name="DEVICE_ROLE_LEAKAGE",
    module="Cleaner/BatchProcessor/FE",
    description="DataFrame 或 Metadata 含 device_role",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="職責違反: device_role 不應出現在 DataFrame",
    recoverable=False
)

E501_DIRECT_WRITE_ATTEMPT = ErrorCode(
    code="E501",
    name="DIRECT_WRITE_ATTEMPT",
    module="Wizard",
    description="試圖直接修改 YAML 檔案",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="安全性違反: 禁止直接寫入 YAML，請使用 Excel",
    recoverable=False
)

# E600-E699: Feature Engineer 錯誤
E601_FEATURE_ORDER_NOT_RECORDED = ErrorCode(
    code="E601",
    name="FEATURE_ORDER_NOT_RECORDED",
    module="FeatureEngineer",
    description="未輸出 feature_order_manifest",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="特徵順序未記錄: 無法保證推論一致性",
    recoverable=False
)

E602_SCALER_PARAMS_MISSING = ErrorCode(
    code="E602",
    name="SCALER_PARAMS_MISSING",
    module="FeatureEngineer",
    description="執行縮放但未輸出縮放參數",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="縮放參數遺失: 推論階段將無法一致縮放",
    recoverable=False
)

E603_FEATURE_MATRIX_SHAPE_ERROR = ErrorCode(
    code="E603",
    name="FEATURE_MATRIX_SHAPE_ERROR",
    module="FeatureEngineer",
    description="特徵矩陣維度異常（如樣本數=0）",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="特徵矩陣形狀錯誤: {shape}",
    recoverable=False
)

E604_INVALID_LAG_CONFIGURATION = ErrorCode(
    code="E604",
    name="INVALID_LAG_CONFIGURATION",
    module="FeatureEngineer",
    description="Lag 設定導致資料長度不足",
    severity=ErrorSeverity.HIGH,
    user_message_template="Lag 設定錯誤: 資料長度 {n} 小於最大 Lag {lag}",
    recoverable=True
)

# E700-E749: Model Training 錯誤
E701_TRAINING_MEMORY_ERROR = ErrorCode(
    code="E701",
    name="TRAINING_MEMORY_ERROR",
    module="ModelTrainer",
    description="GPU/CPU 記憶體不足",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="訓練記憶體不足: {detail}",
    recoverable=False
)

E702_VALIDATION_FAILURE = ErrorCode(
    code="E702",
    name="VALIDATION_FAILURE",
    module="ModelValidator",
    description="驗證集性能低於門檻",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="模型驗證失敗: MAPE {mape}% > 門檻 {threshold}%",
    recoverable=False
)

E703_HYPERPARAMETER_INVALID = ErrorCode(
    code="E703",
    name="HYPERPARAMETER_INVALID",
    module="ModelTrainer",
    description="超參數組合無效",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="無效超參數: {param}={value}",
    recoverable=False
)

E704_CHECKPOINT_SAVE_FAILED = ErrorCode(
    code="E704",
    name="CHECKPOINT_SAVE_FAILED",
    module="ModelTrainer",
    description="模型檢查點儲存失敗",
    severity=ErrorSeverity.HIGH,
    user_message_template="模型儲存失敗: {filepath}",
    recoverable=True
)

E705_CROSS_VALIDATION_ERROR = ErrorCode(
    code="E705",
    name="CROSS_VALIDATION_ERROR",
    module="ModelValidator",
    description="交叉驗證執行失敗",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="交叉驗證錯誤: {detail}",
    recoverable=False
)

E706_MODEL_ARTIFACT_CORRUPTED = ErrorCode(
    code="E706",
    name="MODEL_ARTIFACT_CORRUPTED",
    module="ModelValidator",
    description="輸出模型檔案損毀或不完整",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="模型產物損毀",
    recoverable=False
)

# E750-E759: GNN Topology Errors (v1.2 重分配)
E750_TOPOLOGY_CONTEXT_MISSING = ErrorCode(
    code="E750",
    name="TOPOLOGY_CONTEXT_MISSING",
    module="GNNTrainer",
    description="缺少拓樸上下文 (topology_context)",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="GNN 訓練失敗: 缺少拓樸上下文",
    recoverable=False
)

E751_ADJACENCY_MATRIX_INVALID = ErrorCode(
    code="E751",
    name="ADJACENCY_MATRIX_INVALID",
    module="GNNTrainer",
    description="鄰接矩陣維度與節點數不匹配",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="GNN 鄰接矩陣無效: 維度不匹配",
    recoverable=False
)

E752_NODE_TYPE_MISMATCH = ErrorCode(
    code="E752",
    name="NODE_TYPE_MISMATCH",
    module="GNNTrainer",
    description="節點類型與特徵維度不匹配",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="GNN 節點類型不匹配",
    recoverable=False
)

E753_EDGE_INDEX_OUT_OF_RANGE = ErrorCode(
    code="E753",
    name="EDGE_INDEX_OUT_OF_RANGE",
    module="GNNTrainer",
    description="邊索引超出節點範圍",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="GNN 邊索引超出範圍",
    recoverable=False
)

E754_TOPOLOGY_PROPAGATION_ERROR = ErrorCode(
    code="E754",
    name="TOPOLOGY_PROPAGATION_ERROR",
    module="FeatureEngineer",
    description="Hop-N 拓樸傳播計算錯誤",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="拓樸傳播錯誤: Hop-N 計算失敗",
    recoverable=False
)

E755_GRAPH_FEATURES_MISSING = ErrorCode(
    code="E755",
    name="GRAPH_FEATURES_MISSING",
    module="GNNTrainer",
    description="缺少必要的圖特徵 (node_types/control_semantics)",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="GNN 特徵缺失: 缺少圖結構特徵",
    recoverable=False
)

E756_PHYSICS_LOSS_EXCEEDED = ErrorCode(
    code="E756",
    name="PHYSICS_LOSS_EXCEEDED",
    module="GNNTrainer",
    description="物理守恆損失超過 20% 閾值",
    severity=ErrorSeverity.HIGH,
    user_message_template="物理損失過高: {loss}% > 20%",
    recoverable=True
)

E757_HOP_N_AGGREGATION_DUPLICATE = ErrorCode(
    code="E757",
    name="HOP_N_AGGREGATION_DUPLICATE",
    module="FeatureEngineer",
    description="Hop-N 特徵重複聚合偵測",
    severity=ErrorSeverity.WARNING,
    user_message_template="Hop-N 特徵重複聚合警告",
    recoverable=True
)

E758_GNN_WRAPPER_ERROR = ErrorCode(
    code="E758",
    name="GNN_WRAPPER_ERROR",
    module="GNNTrainer",
    description="Captum GNNWrapper 包裝器錯誤",
    severity=ErrorSeverity.HIGH,
    user_message_template="GNN 解釋器包裝錯誤",
    recoverable=True
)

E759_MULTI_TASK_DIMENSION_MISMATCH = ErrorCode(
    code="E759",
    name="MULTI_TASK_DIMENSION_MISMATCH",
    module="GNNTrainer",
    description="多任務輸出維度與目標數量不匹配",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="多任務維度錯誤: 輸出維度不匹配",
    recoverable=False
)

# E800-E829: Continual Learning 錯誤 (v1.2 新增)
E800_CL_UPDATE_TRIGGERED = ErrorCode(
    code="E800",
    name="CL_UPDATE_TRIGGERED",
    module="UpdateOrchestrator",
    description="CL 更新觸發條件滿足 (綜合評分)",
    severity=ErrorSeverity.INFO,
    user_message_template="CL 更新觸發: {trigger_reason}",
    recoverable=True
)

E801_CL_ABSOLUTE_MAPE_EXCEEDED = ErrorCode(
    code="E801",
    name="CL_ABSOLUTE_MAPE_EXCEEDED",
    module="UpdateOrchestrator",
    description="7天 MAPE 超過 8% 閾值",
    severity=ErrorSeverity.WARNING,
    user_message_template="CL 絕對 MAPE 超標: {mape}% > 8%",
    recoverable=True
)

E802_CL_SCHEDULED_UPDATE = ErrorCode(
    code="E802",
    name="CL_SCHEDULED_UPDATE",
    module="UpdateOrchestrator",
    description="達到定期更新間隔 (30天)",
    severity=ErrorSeverity.INFO,
    user_message_template="CL 定期更新: 距上次更新 {days} 天",
    recoverable=True
)

E803_CL_DRIFT_DETECTED = ErrorCode(
    code="E803",
    name="CL_DRIFT_DETECTED",
    module="DriftDetector",
    description="檢測到概念漂移 (PSI/KS 檢定)",
    severity=ErrorSeverity.WARNING,
    user_message_template="CL 概念漂移檢測: {drift_info}",
    recoverable=True
)

E804_CL_TOPOLOGY_CHANGE = ErrorCode(
    code="E804",
    name="CL_TOPOLOGY_CHANGE",
    module="UpdateOrchestrator",
    description="偵測到拓樸結構變更",
    severity=ErrorSeverity.WARNING,
    user_message_template="CL 拓樸變更: {equipment_id}",
    recoverable=True
)

E805_CL_FALLBACK_PERFORMANCE = ErrorCode(
    code="E805",
    name="CL_FALLBACK_PERFORMANCE",
    module="UpdateOrchestrator",
    description="Fallback 機制啟動，性能下降",
    severity=ErrorSeverity.WARNING,
    user_message_template="CL Fallback 性能: 啟用降級模式",
    recoverable=True
)

E810_CL_GEM_PROJECTION_FAILED = ErrorCode(
    code="E810",
    name="CL_GEM_PROJECTION_FAILED",
    module="GEMTrainer",
    description="梯度投影記憶體 (GEM) 投影失敗",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="CL GEM 投影失敗: {detail}",
    recoverable=False
)

E811_CL_MEMORY_BUFFER_FULL = ErrorCode(
    code="E811",
    name="CL_MEMORY_BUFFER_FULL",
    module="EpisodicMemoryBuffer",
    description="記憶緩衝區已滿，需要修剪",
    severity=ErrorSeverity.HIGH,
    user_message_template="CL 記憶緩衝區已滿",
    recoverable=True
)

E812_CL_IMPORTANCE_SCORE_ERROR = ErrorCode(
    code="E812",
    name="CL_IMPORTANCE_SCORE_ERROR",
    module="EpisodicMemoryBuffer",
    description="重要性評分計算錯誤",
    severity=ErrorSeverity.HIGH,
    user_message_template="CL 重要性評分錯誤",
    recoverable=True
)

E813_CL_MEMORY_VERSION_INCOMPATIBLE = ErrorCode(
    code="E813",
    name="CL_MEMORY_VERSION_INCOMPATIBLE",
    module="GEMTrainer",
    description="記憶緩衝區版本與當前模型不相容",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="CL 記憶版本不相容: 預期 {expected}，實際 {actual}",
    recoverable=False
)

E814_CL_CHECKPOINT_CORRUPTED = ErrorCode(
    code="E814",
    name="CL_CHECKPOINT_CORRUPTED",
    module="GEMTrainer",
    description="CL 檢查點檔案損毀",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="CL 檢查點損毀: {filepath}",
    recoverable=False
)

E815_CL_DISTRIBUTED_LOCK_FAILED = ErrorCode(
    code="E815",
    name="CL_DISTRIBUTED_LOCK_FAILED",
    module="UpdateOrchestrator",
    description="分散式鎖定獲取失敗 (RedisLock 逾時)",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="CL 分散式鎖失敗: 併發更新競爭",
    recoverable=False
)

E820_CL_ONLINE_FINETUNE_TIMEOUT = ErrorCode(
    code="E820",
    name="CL_ONLINE_FINETUNE_TIMEOUT",
    module="GEMTrainer",
    description="線上微調超過 15 分鐘限制",
    severity=ErrorSeverity.HIGH,
    user_message_template="CL 線上微調逾時: {elapsed} > 15min",
    recoverable=True
)

E821_CL_CATASTROPHIC_FORGETTING_DETECTED = ErrorCode(
    code="E821",
    name="CL_CATASTROPHIC_FORGETTING_DETECTED",
    module="GEMTrainer",
    description="偵測到災難性遺忘",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="CL 災難性遺忘偵測: 舊任務性能下降 {drop}%",
    recoverable=False
)

E827_CL_EQUIPMENT_ADDED = ErrorCode(
    code="E827",
    name="CL_EQUIPMENT_ADDED",
    module="UpdateOrchestrator",
    description="偵測到新設備加入",
    severity=ErrorSeverity.INFO,
    user_message_template="CL 新設備加入: {equipment_id}",
    recoverable=True
)

E828_CL_EQUIPMENT_REMOVED = ErrorCode(
    code="E828",
    name="CL_EQUIPMENT_REMOVED",
    module="UpdateOrchestrator",
    description="偵測到設備移除",
    severity=ErrorSeverity.WARNING,
    user_message_template="CL 設備移除: {equipment_id}",
    recoverable=True
)

E829_CL_EQUIPMENT_MAINTENANCE = ErrorCode(
    code="E829",
    name="CL_EQUIPMENT_MAINTENANCE",
    module="UpdateOrchestrator",
    description="設備維護模式觸發",
    severity=ErrorSeverity.INFO,
    user_message_template="CL 設備維護: {equipment_id}",
    recoverable=True
)

# E840-E859: Optimization 錯誤 (v1.2 遷移自 E800-E808)
E841_MODEL_REGISTRY_MISSING = ErrorCode(
    code="E841",
    name="MODEL_REGISTRY_MISSING",
    module="OptimizationEngine",
    description="Model Registry Index 不存在或模型檔案遺失",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="模型載入失敗: {model_path}",
    recoverable=False
)

E842_CONSTRAINT_VIOLATION = ErrorCode(
    code="E842",
    name="CONSTRAINT_VIOLATION",
    module="OptimizationEngine",
    description="設備邏輯約束無法滿足",
    severity=ErrorSeverity.HIGH,
    user_message_template="約束違反: {constraint_detail}",
    recoverable=True
)

E843_OPTIMIZATION_DIVERGENCE = ErrorCode(
    code="E843",
    name="OPTIMIZATION_DIVERGENCE",
    module="OptimizationEngine",
    description="求解器無法收斂",
    severity=ErrorSeverity.HIGH,
    user_message_template="最佳化發散: {solver_status}",
    recoverable=True
)

E844_BOUND_INFEASIBILITY = ErrorCode(
    code="E844",
    name="BOUND_INFEASIBILITY",
    module="OptimizationEngine",
    description="變數邊界設定導致無解",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="邊界不可行: {variable}",
    recoverable=False
)

E845_FORECAST_HORIZON_MISMATCH = ErrorCode(
    code="E845",
    name="FORECAST_HORIZON_MISMATCH",
    module="OptimizationEngine",
    description="預測時程與最佳化時程不匹配",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="預測時程錯誤: 需 {required} 步，得 {actual} 步",
    recoverable=False
)

E846_SYSTEM_MODEL_DISCREPANCY = ErrorCode(
    code="E846",
    name="SYSTEM_MODEL_DISCREPANCY",
    module="OptimizationEngine",
    description="System Model 與 Component Models 加總差異 > 5%",
    severity=ErrorSeverity.HIGH,
    user_message_template="模型不一致: 系統級與元件級預測差異 {diff}%",
    recoverable=True
)

E847_EQUIPMENT_STATE_INVALID = ErrorCode(
    code="E847",
    name="EQUIPMENT_STATE_INVALID",
    module="OptimizationEngine",
    description="設備狀態違反物理邏輯（如主機開但水泵關）",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="設備狀態無效: {equipment_logic}",
    recoverable=False
)

E848_WEATHER_DATA_MISSING = ErrorCode(
    code="E848",
    name="WEATHER_DATA_MISSING",
    module="OptimizationEngine",
    description="缺少未來天氣預測資料",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="天氣資料缺失: 無法執行未來 {hours} 小時最佳化",
    recoverable=False
)

# E850-E859: Optimization 擴展錯誤 (v1.2 新增)
E850_CRITICAL_MODEL_MISMATCH = ErrorCode(
    code="E850",
    name="CRITICAL_MODEL_MISMATCH",
    module="OptimizationEngine",
    description="System vs Component 差異 > 15% (嚴重不匹配)",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="模型嚴重不匹配: 差異 {diff}% > 15%",
    recoverable=False
)

E851_FALLBACK_LEVEL_TRIGGERED = ErrorCode(
    code="E851",
    name="FALLBACK_LEVEL_TRIGGERED",
    module="FallbackHandler",
    description="Fallback 降級機制已觸發",
    severity=ErrorSeverity.WARNING,
    user_message_template="Fallback 降級: 當前層級 {level}",
    recoverable=True
)

E852_WARM_START_UNAVAILABLE = ErrorCode(
    code="E852",
    name="WARM_START_UNAVAILABLE",
    module="OptimizationEngine",
    description="暖啟動資料不可用",
    severity=ErrorSeverity.HIGH,
    user_message_template="暖啟動不可用: 使用冷啟動",
    recoverable=True
)

# E900-E999: 跨階段整合錯誤
E901_FEATURE_ALIGNMENT_MISMATCH = ErrorCode(
    code="E901",
    name="FEATURE_ALIGNMENT_MISMATCH",
    module="Optimization",
    description="推論特徵順序/名稱與訓練時不一致",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="特徵對齊錯誤: 索引 {index} 預期 '{expected}'，實際 '{actual}'",
    recoverable=False
)

E902_FEATURE_DIMENSION_MISMATCH = ErrorCode(
    code="E902",
    name="FEATURE_DIMENSION_MISMATCH",
    module="Optimization",
    description="推論特徵維度與訓練時不同",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="特徵維度錯誤: 訓練 {train_dim} 維，輸入 {input_dim} 維",
    recoverable=False
)

E903_SCALER_MISMATCH = ErrorCode(
    code="E903",
    name="SCALER_MISMATCH",
    module="Optimization",
    description="縮放參數與特徵不匹配或缺失",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="縮放參數錯誤: {detail}",
    recoverable=False
)

E904_EQUIPMENT_CONSTRAINT_INCONSISTENT = ErrorCode(
    code="E904",
    name="EQUIPMENT_CONSTRAINT_INCONSISTENT",
    module="Optimization",
    description="當前設備限制與訓練時不一致",
    severity=ErrorSeverity.HIGH,
    user_message_template="設備限制不一致: 訓練使用 {train_constraints}，當前使用 {current_constraints}",
    recoverable=True
)

E905_MODEL_VERSION_INCOMPATIBLE = ErrorCode(
    code="E905",
    name="MODEL_VERSION_INCOMPATIBLE",
    module="Optimization",
    description="模型版本與 Optimization 引擎不相容",
    severity=ErrorSeverity.CRITICAL,
    user_message_template="模型版本不相容: 模型 v{model_ver}，引擎需 >= {engine_ver}",
    recoverable=False
)

E906_PIPELINE_VERSION_DRIFT = ErrorCode(
    code="E906",
    name="PIPELINE_VERSION_DRIFT",
    module="Container",
    description="跨模組版本組合未通過相容性矩陣驗證",
    severity=ErrorSeverity.HIGH,
    user_message_template="版本漂移: {module_a} v{ver_a} 與 {module_b} v{ver_b} 不相容",
    recoverable=True
)


# 錯誤代碼字典 (方便查詢)
ERROR_CODES: Dict[str, ErrorCode] = {
    # E000
    "E000": E000_TEMPORAL_BASELINE_MISSING,
    "E000-W": E000W_TEMPORAL_DRIFT_WARNING,
    # E001-E099
    "E001": E001_ENCODING_MISMATCH,
    "E006": E006_MEMORY_LIMIT_EXCEEDED,
    "E007": E007_CONFIG_FILE_CORRUPTED,
    # E100-E199
    "E101": E101_ENCODING_MISMATCH,
    "E102": E102_TIMEZONE_VIOLATION,
    "E103": E103_CONTRACT_VIOLATION,
    "E104": E104_HEADER_NOT_FOUND,
    "E105": E105_HEADER_STANDARDIZATION_FAILED,
    "E111": E111_TIMEZONE_WARNING,
    "E112": E112_FUTURE_DATA_DETECTED,
    # E200-E299
    "E201": E201_INPUT_SCHEMA_MISMATCH,
    "E202": E202_UNKNOWN_QUALITY_FLAG,
    "E203": E203_METADATA_LOSS,
    "E205": E205_FUTURE_DATA_IN_BATCH,
    "E206": E206_PARQUET_FORMAT_VIOLATION,
    "E210": E210_PHYSICAL_CONSTRAINT_VIOLATION,
    "E211": E211_FROZEN_DATA_DETECTED,
    "E212": E212_ZERO_RATIO_EXCEEDED,
    "E213": E213_INSUFFICIENT_DATA_GAP,
    # E300-E349
    "E301": E301_MANIFEST_INTEGRITY_FAILED,
    "E302": E302_SCHEMA_MISMATCH,
    "E303": E303_UNKNOWN_QUALITY_FLAG,
    "E304": E304_METADATA_MISSING,
    "E305": E305_DATA_LEAKAGE_DETECTED,
    "E306": E306_DYNAMIC_GLOBAL_MEAN_RISK,
    # E350-E399
    "E350": E350_EQUIPMENT_LOGIC_PRECHECK_FAILED,
    "E351": E351_EQUIPMENT_VALIDATION_AUDIT_MISSING,
    "E352": E352_EQUIPMENT_CONSTRAINT_MISMATCH,
    "E353": E353_REQUIRES_VIOLATION,
    "E354": E354_MUTEX_VIOLATION,
    "E355": E355_SEQUENCE_VIOLATION,
    "E356": E356_MIN_RUNTIME_VIOLATION,
    "E357": E357_MIN_DOWNTIME_VIOLATION,
    # E400-E499
    "E400": E400_ANNOTATION_VERSION_MISMATCH,
    "E401": E401_ORPHAN_COLUMN,
    "E402": E402_UNANNOTATED_COLUMN,
    "E403": E403_UNIT_INCOMPATIBLE,
    "E404": E404_LAG_FORMAT_INVALID,
    "E405": E405_TARGET_LEAKAGE_RISK,
    "E406": E406_EXCEL_YAML_OUT_OF_SYNC,
    "E407": E407_CIRCULAR_INHERITANCE,
    "E408": E408_SSOT_QUALITY_FLAGS_MISMATCH,
    "E409": E409_HEADER_ANNOTATION_MISMATCH,
    # E500-E599
    "E500": E500_DEVICE_ROLE_LEAKAGE,
    "E501": E501_DIRECT_WRITE_ATTEMPT,
    # E600-E699
    "E601": E601_FEATURE_ORDER_NOT_RECORDED,
    "E602": E602_SCALER_PARAMS_MISSING,
    "E603": E603_FEATURE_MATRIX_SHAPE_ERROR,
    "E604": E604_INVALID_LAG_CONFIGURATION,
    # E700-E749
    "E701": E701_TRAINING_MEMORY_ERROR,
    "E702": E702_VALIDATION_FAILURE,
    "E703": E703_HYPERPARAMETER_INVALID,
    "E704": E704_CHECKPOINT_SAVE_FAILED,
    "E705": E705_CROSS_VALIDATION_ERROR,
    "E706": E706_MODEL_ARTIFACT_CORRUPTED,
    # E750-E759: GNN Topology Errors
    "E750": E750_TOPOLOGY_CONTEXT_MISSING,
    "E751": E751_ADJACENCY_MATRIX_INVALID,
    "E752": E752_NODE_TYPE_MISMATCH,
    "E753": E753_EDGE_INDEX_OUT_OF_RANGE,
    "E754": E754_TOPOLOGY_PROPAGATION_ERROR,
    "E755": E755_GRAPH_FEATURES_MISSING,
    "E756": E756_PHYSICS_LOSS_EXCEEDED,
    "E757": E757_HOP_N_AGGREGATION_DUPLICATE,
    "E758": E758_GNN_WRAPPER_ERROR,
    "E759": E759_MULTI_TASK_DIMENSION_MISMATCH,
    # E800-E829: Continual Learning Errors
    "E800": E800_CL_UPDATE_TRIGGERED,
    "E801": E801_CL_ABSOLUTE_MAPE_EXCEEDED,
    "E802": E802_CL_SCHEDULED_UPDATE,
    "E803": E803_CL_DRIFT_DETECTED,
    "E804": E804_CL_TOPOLOGY_CHANGE,
    "E805": E805_CL_FALLBACK_PERFORMANCE,
    "E810": E810_CL_GEM_PROJECTION_FAILED,
    "E811": E811_CL_MEMORY_BUFFER_FULL,
    "E812": E812_CL_IMPORTANCE_SCORE_ERROR,
    "E813": E813_CL_MEMORY_VERSION_INCOMPATIBLE,
    "E814": E814_CL_CHECKPOINT_CORRUPTED,
    "E815": E815_CL_DISTRIBUTED_LOCK_FAILED,
    "E820": E820_CL_ONLINE_FINETUNE_TIMEOUT,
    "E821": E821_CL_CATASTROPHIC_FORGETTING_DETECTED,
    "E827": E827_CL_EQUIPMENT_ADDED,
    "E828": E828_CL_EQUIPMENT_REMOVED,
    "E829": E829_CL_EQUIPMENT_MAINTENANCE,
    # E840-E859: Optimization Errors (migrated from E800-E808)
    "E841": E841_MODEL_REGISTRY_MISSING,
    "E842": E842_CONSTRAINT_VIOLATION,
    "E843": E843_OPTIMIZATION_DIVERGENCE,
    "E844": E844_BOUND_INFEASIBILITY,
    "E845": E845_FORECAST_HORIZON_MISMATCH,
    "E846": E846_SYSTEM_MODEL_DISCREPANCY,
    "E847": E847_EQUIPMENT_STATE_INVALID,
    "E848": E848_WEATHER_DATA_MISSING,
    "E850": E850_CRITICAL_MODEL_MISMATCH,
    "E851": E851_FALLBACK_LEVEL_TRIGGERED,
    "E852": E852_WARM_START_UNAVAILABLE,
    # E900-E999
    "E901": E901_FEATURE_ALIGNMENT_MISMATCH,
    "E902": E902_FEATURE_DIMENSION_MISMATCH,
    "E903": E903_SCALER_MISMATCH,
    "E904": E904_EQUIPMENT_CONSTRAINT_INCONSISTENT,
    "E905": E905_MODEL_VERSION_INCOMPATIBLE,
    "E906": E906_PIPELINE_VERSION_DRIFT,
}


def get_error_code(code: str) -> Optional[ErrorCode]:
    """根據錯誤代碼取得錯誤定義"""
    return ERROR_CODES.get(code)


def format_error_message(code: str, **kwargs) -> str:
    """格式化錯誤訊息"""
    error = ERROR_CODES.get(code)
    if error:
        return error.user_message_template.format(**kwargs)
    return f"未知錯誤代碼: {code}"


# =============================================================================
# 2. 品質標記定義 (VALID_QUALITY_FLAGS)
# =============================================================================

VALID_QUALITY_FLAGS: List[str] = [
    # 資料品質標記
    "RAW",                      # 原始資料
    "VALIDATED",               # 已驗證
    "CLEANED",                 # 已清洗
    "INTERPOLATED",            # 已插值
    "OUTLIER_REMOVED",         # 異常值已移除
    "PHYSICAL_IMPOSSIBLE",     # 物理上不可能
    "EQUIPMENT_VIOLATION",     # 設備邏輯違規
    "FROZEN",                  # 凍結資料（連續相同值）
    "FROZEN_DATA",             # 凍結資料（Cleaner v2.2 使用）
    "ZERO_VALUE_EXCESS",       # 零值過多（Cleaner v2.2 使用）
    "PHYSICAL_LIMIT_VIOLATION", # 物理限制違規（Cleaner v2.2 使用）
    "FUTURE_DATA",             # 未來資料（Cleaner v2.2 使用）
    "TIMEZONE_MISMATCH",       # 時區不匹配
    "DST_GAP",                 # 夏令時間隙
    "FORMAT_INVALID",          # 格式無效
    "ENCODING_ERROR",          # 編碼錯誤
    "INSUFFICIENT_DATA",       # 資料不足
    "MISSING_VALUE",           # 缺值
    "SENSOR_ERROR",            # 感測器錯誤
    "MANUAL_OVERRIDE",         # 手動覆蓋
    "CALCULATED",              # 計算值
    "ESTIMATED",               # 估計值
    "FORECAST",                # 預測值
    "EXTRAPOLATED",            # 外插值
    "FLAGGED_FOR_REVIEW",      # 標記待審查
    "REJECTED",                # 已拒絕
    "DUPLICATE",               # 重複資料
    "TIME_SHIFTED",            # 時間已調整
]

# 品質標記集合（用於快速查詢）
VALID_QUALITY_FLAGS_SET: Set[str] = set(VALID_QUALITY_FLAGS)

# 品質標記版本（供 E408 驗證使用）
VALID_QUALITY_FLAGS_VERSION: str = "1.3.0"


def validate_quality_flags(flags: List[str]) -> Tuple[bool, List[str]]:
    """
    驗證品質標記是否有效
    
    Returns:
        (是否有效, 無效標記列表)
    """
    invalid = [f for f in flags if f not in VALID_QUALITY_FLAGS_SET]
    return len(invalid) == 0, invalid


# =============================================================================
# 3. 時間戳規格 (TIMESTAMP_CONFIG)
# =============================================================================

TIMESTAMP_CONFIG: Dict[str, Any] = {
    "format": "ISO 8601 UTC",
    "polars_dtype": "pl.Datetime(time_unit='ns', time_zone='UTC')",
    "parquet_physical_type": "INT64",           # 強制使用 INT64，禁止使用 INT96
    "parquet_logical_type": "TIMESTAMP(NANOS, UTC)",
    "unit": "nanoseconds",                      # 奈秒級精度
    "timezone": "UTC",                          # 強制 UTC 時區
    "naive_timezone": False,                    # 禁止無時區資料
    "allowed_units": ["nanoseconds", "ns"],     # 允許的時間單位
    "forbidden_units": ["microseconds", "us", "milliseconds", "ms", "seconds", "s"],
    "datetime_column_name": "timestamp",        # 強制欄位名稱
    "alternative_names": ["time", "date", "datetime"],  # 需要正規化的替代名稱
}


# =============================================================================
# 4. Feature Annotation 常數
# =============================================================================

FEATURE_ANNOTATION_CONSTANTS: Dict[str, Any] = {
    "expected_schema_version": "1.3",
    "expected_template_version": "1.3",
    "supported_schema_versions": ["1.2", "1.3"],
    "yaml_schema_file": "config/features/schema.json",
    "excel_template_file": "tools/features/templates/Feature_Template_v1.3.xlsx",
    "equipment_taxonomy_file": "config/features/equipment_taxonomy.yaml",
    "checksum_algorithm": "sha256",
    "inheritance_max_depth": 10,                 # 防止無限繼承
    "reserved_column_names": [                   # 禁止作為欄位名稱
        "timestamp",
        "quality_flags",
        "__index_level_0__",
    ],
    "device_role_values": [                      # 設備角色允許值
        "primary",
        "backup",
        "seasonal",
        "auxiliary",
        "standby",
    ],
    "physical_types": [                          # 物理類型允許值
        "temperature", "pressure", "flow_rate", "power", 
        "frequency", "status", "efficiency", "count", 
        "ratio", "other", "chiller_load", "gauge", 
        "cooling_capacity", "energy", "valve_position", 
        "rotational_speed", "current", "voltage", 
        "power_factor", "pressure_differential", "operating_status"
    ],
    "units": {                                   # 單位對應
        "temperature": ["°C", "°F", "K"],
        "pressure": ["bar", "psi", "kPa", "Pa"],
        "flow_rate": ["LPM", "GPM", "m³/h", "L/s"],
        "power": ["kW", "W", "MW", "hp"],
        "frequency": ["Hz"],
        "status": ["on/off", "0/1", "boolean"],
        "efficiency": ["kW/RT", "COP", "%"],
        "count": ["count", "pcs", "units"],
        "ratio": ["%", "ratio", "p.u."],
    },
}


# =============================================================================
# 5. Header Standardization 規則
# =============================================================================

HEADER_STANDARDIZATION_RULES: List[Tuple[str, Any]] = [
    # 步驟 1: 移除前後空白
    (r'^\s+|\s+$', ''),
    
    # 步驟 2: 將 camelCase/PascalCase 轉換為 snake_case
    # 插入底線在大寫字母前，然後轉小寫
    (r'(?<=[a-z0-9])(?=[A-Z])', '_'),      # 在小寫/數字後的大寫前插入底線
    (r'(?<=[A-Z])(?=[A-Z][a-z])', '_'),    # 在連續大寫中的第二個大寫前插入底線
    
    # 步驟 3: 替換非法字元為底線
    (r'[^a-zA-Z0-9_]', '_'),               # 非字母數字底線的字元替換為底線
    
    # 步驟 4: 合併連續底線
    (r'_+', '_'),
    
    # 步驟 5: 移除開頭數字（Python 變數限制）
    (r'^[0-9]+', 'col_'),
    
    # 步驟 6: 轉換為小寫
    (r'[A-Z]', lambda m: m.group(0).lower()),
]


class HeaderStandardizationError(Exception):
    """標頭正規化錯誤"""
    pass


def standardize_header(header: str) -> str:
    """
    將 CSV 標頭正規化為 snake_case
    
    Args:
        header: 原始標頭字串
        
    Returns:
        正規化後的標頭
        
    Raises:
        HeaderStandardizationError: 若正規化後仍不符合規則
    """
    result = header
    
    for pattern, replacement in HEADER_STANDARDIZATION_RULES:
        if callable(replacement):
            result = re.sub(pattern, replacement, result)
        else:
            result = re.sub(pattern, replacement, result)
    
    # 驗證結果
    if not result or result == '_' or not re.match(r'^[a-z][a-z0-9_]*$', result):
        raise HeaderStandardizationError(
            f"E105: 標頭 '{header}' 無法正規化為有效識別符，結果: '{result}'"
        )
    
    return result


# =============================================================================
# 6. 設備驗證限制條件
# =============================================================================

EQUIPMENT_VALIDATION_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
    "chiller_pump_mutex": {
        "description": "主機開啟時必須有至少一台冷卻水泵運轉",
        "check_type": "requires",
        "trigger": "chiller_1_status == 1 OR chiller_2_status == 1",
        "requirement": "pump_1_status == 1 OR pump_2_status == 1",
        "severity": "critical",
        "error_code": "E350",
        "quality_flag": "PHYSICAL_IMPOSSIBLE",
    },
    "min_runtime_15min": {
        "description": "主機開啟後至少運轉 15 分鐘才能關閉",
        "check_type": "sequence",
        "min_duration_minutes": 15,
        "applies_to": ["chiller_1_status", "chiller_2_status"],
        "severity": "warning",
        "error_code": "E356",
        "quality_flag": "EQUIPMENT_VIOLATION",
    },
    "min_downtime_10min": {
        "description": "主機關閉後至少停機 10 分鐘才能再次開啟",
        "check_type": "sequence",
        "min_duration_minutes": 10,
        "applies_to": ["chiller_1_status", "chiller_2_status"],
        "severity": "warning",
        "error_code": "E357",
        "quality_flag": "EQUIPMENT_VIOLATION",
    },
    "chiller_exclusion": {
        "description": "互斥：主機1與主機2在同一時間只能有一台運轉（若為互斥配置）",
        "check_type": "mutex",
        "equipment": ["chiller_1_status", "chiller_2_status"],
        "severity": "warning",
        "error_code": "E354",
        "quality_flag": "EQUIPMENT_VIOLATION",
        "enabled_by_config": True,  # 需由配置啟用
    },
    "pump_redundancy": {
        "description": "冗餘要求：若主機運轉，必須有至少一台冷凍水泵和一台冷卻水泵運轉",
        "check_type": "requires",
        "trigger": "chiller_1_status == 1 OR chiller_2_status == 1",
        "requirement": "(chw_pump_1_status == 1 OR chw_pump_2_status == 1) AND (cw_pump_1_status == 1 OR cw_pump_2_status == 1)",
        "severity": "critical",
        "error_code": "E350",
        "quality_flag": "PHYSICAL_IMPOSSIBLE",
    },
    "ct_fan_sequence": {
        "description": "冷卻水塔風機開啟順序：必須先開啟冷卻水泵再開啟風機",
        "check_type": "sequence",
        "prerequisite": "cw_pump_status",
        "dependent": "ct_fan_status",
        "severity": "warning",
        "error_code": "E355",
        "quality_flag": "EQUIPMENT_VIOLATION",
    },
}


# =============================================================================
# 7. Pipeline 時間基準傳遞 (Temporal Baseline)
# =============================================================================

class TemporalContext:
    """
    全域時間基準容器（Thread-safe Singleton）
    
    使用方式:
        context = TemporalContext()
        baseline = context.get_baseline()
        if context.is_future(timestamp):
            raise Exception("未來資料")
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
                    cls._instance.origin_timestamp = None
                    cls._instance.baseline_version = "1.0"
        return cls._instance
    
    def initialize(self, timestamp: Optional[datetime] = None):
        """初始化時間基準（僅可執行一次）"""
        if self._initialized:
            raise RuntimeError("TemporalContext 已初始化，不可重複設定")
        
        self.origin_timestamp = timestamp or datetime.now(timezone.utc)
        self._initialized = True
    
    def get_baseline(self) -> datetime:
        """取得 Pipeline 啟動時間戳"""
        if not self._initialized:
            raise RuntimeError(
                f"{E000_TEMPORAL_BASELINE_MISSING.code}: "
                f"{E000_TEMPORAL_BASELINE_MISSING.user_message_template}"
            )
        return self.origin_timestamp
    
    def is_future(self, timestamp: datetime, tolerance_minutes: int = 5) -> bool:
        """
        判斷時間戳是否為「未來資料」
        
        標準：timestamp > origin_timestamp + tolerance_minutes
        """
        if not self._initialized:
            raise RuntimeError("TemporalContext 未初始化")
        
        threshold = self.origin_timestamp + timedelta(minutes=tolerance_minutes)
        return timestamp > threshold
    
    def get_elapsed_minutes(self) -> float:
        """取得 Pipeline 已執行時間（用於漂移檢測）"""
        if not self._initialized:
            raise RuntimeError("TemporalContext 未初始化")
        
        return (datetime.now(timezone.utc) - self.origin_timestamp).total_seconds() / 60
    
    def check_drift_warning(self) -> Optional[str]:
        """檢查是否需要發出時間漂移警告"""
        elapsed = self.get_elapsed_minutes()
        if elapsed > 60:
            return E000W_TEMPORAL_DRIFT_WARNING.user_message_template
        return None
    
    def to_dict(self) -> Dict[str, str]:
        """轉換為字典格式（用於傳遞）"""
        return {
            "pipeline_origin_timestamp": self.origin_timestamp.isoformat() if self.origin_timestamp else None,
            "timezone": "UTC",
            "baseline_version": self.baseline_version,
        }
    
    @classmethod
    def reset_for_testing(cls):
        """重置單例（僅供測試使用）"""
        cls._instance = None


# =============================================================================
# 8. 版本相容性矩陣
# =============================================================================

VERSION_COMPATIBILITY_MATRIX: List[Dict[str, Any]] = [
    {
        "parser": "v2.1",
        "cleaner": "v2.2",
        "batch_processor": "v1.3",
        "feature_engineer": "v1.3",
        "model_training": "v1.2",
        "optimization": "v1.1",
        "equipment_validation": "v1.0",
        "compatibility": "full",  # 🟢 完全相容
        "notes": "推薦配置，支援特徵對齊驗證 E901-E903，設備邏輯同步",
    },
    {
        "parser": "v2.1",
        "cleaner": "v2.2",
        "batch_processor": "v1.3",
        "feature_engineer": "v1.3",
        "model_training": "v1.2",
        "optimization": "v1.0",
        "equipment_validation": "v1.0",
        "compatibility": "incompatible",  # 🔴 不相容
        "notes": "Optimization v1.0 缺少特徵對齊檢查點 #7",
    },
    {
        "parser": "v2.1",
        "cleaner": "v2.2",
        "batch_processor": "v1.3",
        "feature_engineer": "v1.2",
        "model_training": "v1.2",
        "optimization": "v1.1",
        "equipment_validation": "v1.0",
        "compatibility": "partial",  # 🟡 部分相容
        "notes": "FE v1.2 無法輸出 feature_order_manifest，觸發 E601",
    },
    {
        "parser": "v2.1",
        "cleaner": "v2.2",
        "batch_processor": "v1.3",
        "feature_engineer": "v1.3",
        "model_training": "v1.1",
        "optimization": "v1.1",
        "equipment_validation": "v1.0",
        "compatibility": "partial",  # 🟡 部分相容
        "notes": "Training v1.1 未輸出 scaler_params，Optimization 使用預設值",
    },
    {
        "parser": "v2.1",
        "cleaner": "v2.1",
        "batch_processor": "v1.3",
        "feature_engineer": "v1.3",
        "model_training": "v1.2",
        "optimization": "v1.1",
        "equipment_validation": "v1.0",
        "compatibility": "incompatible",  # 🔴 不相容
        "notes": "Cleaner v2.1 可能輸出 device_role，觸發 E500",
    },
]


def check_version_compatibility(
    parser: str,
    cleaner: str,
    batch_processor: str,
    feature_engineer: str,
    model_training: str,
    optimization: str,
    equipment_validation: str = "v1.0"
) -> Tuple[str, str]:
    """
    檢查版本相容性
    
    Returns:
        (相容性等級, 說明)
        相容性等級: "full" | "partial" | "incompatible"
    """
    current_versions = {
        "parser": parser,
        "cleaner": cleaner,
        "batch_processor": batch_processor,
        "feature_engineer": feature_engineer,
        "model_training": model_training,
        "optimization": optimization,
        "equipment_validation": equipment_validation,
    }
    
    for config in VERSION_COMPATIBILITY_MATRIX:
        matches = all(
            current_versions.get(key) == config.get(key)
            for key in ["parser", "cleaner", "batch_processor", 
                       "feature_engineer", "model_training", "optimization"]
        )
        if matches:
            return config["compatibility"], config["notes"]
    
    # 未找到匹配，視為不相容
    return "incompatible", "版本組合未定義於相容性矩陣"


# =============================================================================
# 9. 檢查點規格常數
# =============================================================================

CHECKPOINTS: Dict[str, Dict[str, Any]] = {
    "#1": {
        "name": "Parser → Cleaner (Raw Data Contract)",
        "location": "src/etl/parser.py _validate_output_contract",
        "validations": [
            {"item": "必要欄位", "spec": "必須包含 timestamp", "error_code": "E003"},
            {"item": "時間戳型別", "spec": "pl.Datetime(time_unit='ns', time_zone='UTC')", "error_code": "E002"},
            {"item": "時間戳物理型別", "spec": "Parquet 層級必須為 INT64", "error_code": "E002"},
            {"item": "編碼正確性", "spec": "無 UTF-8 BOM 殘留", "error_code": "E001"},
            {"item": "標頭正規化", "spec": "欄位名稱必須符合 Header Standardization 規則", "error_code": "E105"},
            {"item": "時間基準繼承", "spec": "必須接收並傳遞 pipeline_origin_timestamp", "error_code": "E000"},
        ]
    },
    "#2": {
        "name": "Cleaner → BatchProcessor (Clean Data Contract)",
        "location": "src/etl/cleaner.py _validate_output_contract",
        "validations": [
            {"item": "Quality Flags 型別", "spec": "pl.List(pl.Utf8)", "error_code": "E201"},
            {"item": "Quality Flags 值域", "spec": "所有值必須 ∈ VALID_QUALITY_FLAGS", "error_code": "E202"},
            {"item": "禁止欄位檢查", "spec": "不可包含 device_role, ignore_warnings, is_target", "error_code": "E500"},
            {"item": "未來資料檢查", "spec": "時間戳不可超過 pipeline_origin_timestamp + 5分鐘", "error_code": "E102"},
            {"item": "物理邏輯預檢", "spec": "若啟用，必須通過基礎設備邏輯檢查", "error_code": "E350"},
        ]
    },
    "#3": {
        "name": "BatchProcessor → FeatureEngineer (Storage Contract)",
        "location": "src/etl/batch_processor.py _verify_parquet_schema",
        "validations": [
            {"item": "Parquet Schema", "spec": "timestamp 物理型別必須為 INT64", "error_code": "E206"},
            {"item": "未來資料防護", "spec": "批次時間範圍不可超過 temporal_baseline + 5分鐘", "error_code": "E205"},
            {"item": "device_role 不存在", "spec": "Parquet Schema 與 DataFrame 皆不可含此欄位", "error_code": "E500"},
            {"item": "時間基準存在性", "spec": "必須包含 temporal_baseline 欄位", "error_code": "E000"},
            {"item": "物理邏輯稽核", "spec": "若啟用，必須包含 equipment_validation_audit", "error_code": "E351"},
        ]
    },
    "#4": {
        "name": "FeatureEngineer → Model Training (Feature Matrix Contract)",
        "location": "src/etl/feature_engineer.py 輸出驗證",
        "validations": [
            {"item": "Data Leakage 檢查", "spec": "特徵欄位不可包含目標變數的未來資訊", "error_code": "E305"},
            {"item": "特徵順序保證", "spec": "輸出 feature_order_manifest 記錄欄位順序", "error_code": "E601"},
            {"item": "特徵縮放參數", "spec": "若執行縮放，必須輸出 scaler_params", "error_code": "E602"},
            {"item": "時間基準傳遞", "spec": "必須將 pipeline_origin_timestamp 寫入 metadata", "error_code": "E000"},
            {"item": "設備邏輯特徵一致性", "spec": "設備狀態特徵必須與 Equipment Validation 邏輯一致", "error_code": "E352"},
        ]
    },
    "#5": {
        "name": "Excel ↔ YAML 同步檢查 (Annotation Sync Contract)",
        "location": "src/utils/config_loader.py validate_annotation_sync",
        "validations": [
            {"item": "檔案存在性", "spec": "Excel 與 YAML 必須同時存在", "error_code": "E406"},
            {"item": "時間戳同步", "spec": "mtime(excel) ≤ mtime(yaml)", "error_code": "E406"},
            {"item": "Checksum 一致性", "spec": "YAML 中記錄的 excel_checksum 必須與實際相符", "error_code": "E406"},
            {"item": "SSOT 常數同步", "spec": "YAML 中的 quality_flags_reference 必須與 VALID_QUALITY_FLAGS 一致", "error_code": "E408"},
        ]
    },
    "#6": {
        "name": "Annotation Schema 版本相容 (Schema Compatibility Contract)",
        "location": "src/features/annotation_manager.py",
        "validations": [
            {"item": "Schema 版本", "spec": "schema_version 必須等於 expected_schema_version", "error_code": "E400"},
            {"item": "繼承鏈合法性", "spec": "inherit 指向的父檔案必須存在，且不可造成循環繼承", "error_code": "E407"},
            {"item": "Header 對應檢查", "spec": "YAML 中的 column_name 必須與實際 CSV 標頭（經正規化後）匹配", "error_code": "E409"},
        ]
    },
    "#7": {
        "name": "Model Training → Optimization (Model Artifact & Feature Alignment Contract)",
        "location": "src/training/output_validator.py 與 src/optimization/input_validator.py",
        "validations": [
            {"item": "模型格式", "spec": "必須為 .joblib 或 .onnx，且包含 feature_order_manifest", "error_code": "E701"},
            {"item": "特徵順序比對", "spec": "Optimization 輸入特徵順序必須與 Training 完全一致", "error_code": "E901"},
            {"item": "特徵數量一致性", "spec": "輸入特徵維度必須等於模型訓練時的維度", "error_code": "E902"},
            {"item": "縮放參數對齊", "spec": "scaler_params.feature_names 順序必須與 feature_order_manifest.features 一致", "error_code": "E903"},
            {"item": "設備限制一致性", "spec": "Optimization 使用的設備限制必須與 Training 時記錄的相容", "error_code": "E904"},
        ]
    },
}


# =============================================================================
# 10. DataFrame 介面標準
# =============================================================================

DATAFRAME_INTERFACE_STANDARD: Dict[str, Any] = {
    "timestamp_column": {
        "name": "timestamp",
        "polars_dtype": "pl.Datetime(time_unit='ns', time_zone='UTC')",
        "parquet_physical_type": "INT64",
        "parquet_logical_type": "TIMESTAMP(NANOS, UTC)",
        "forbidden_alternatives": ["time", "date", "datetime"],
    },
    "quality_flags_column": {
        "name": "quality_flags",
        "polars_dtype": "pl.List(pl.Utf8)",
        "parquet_storage": "JSON string as BYTE_ARRAY",
        "valid_values": VALID_QUALITY_FLAGS,
    },
    "numeric_columns": {
        "polars_dtype": "pl.Float64",
        "unit_encoding": "SI units only, NOT in column names",
        "null_representation": "Polars null (not NaN or magic numbers)",
        "precision": "at least 6 significant digits",
    },
    "forbidden_columns": [
        "device_role",
        "ignore_warnings", 
        "is_target",
        "__index_level_0__",
    ],
    "allowed_metadata_keys": [
        "column_name",
        "physical_type",
        "unit",
        "description",
        "precision",
        "temporal_baseline",
    ],
    "forbidden_metadata_keys": [
        "device_role",
        "ignore_warnings",
        "is_target",
        "valid_range",
    ],
}


# =============================================================================
# 11. 實作檢查清單
# =============================================================================

IMPLEMENTATION_CHECKLIST: Dict[str, List[str]] = {
    "pre_development": [
        "所有模組 PRD 引用本文件作為「檢查點」與「錯誤代碼」的 SSOT",
        "src/etl/config_models.py 已定義 VALID_QUALITY_FLAGS, TIMESTAMP_CONFIG, FEATURE_ANNOTATION_CONSTANTS",
        "src/etl/config_models.py 已定義 HEADER_STANDARDIZATION_RULES",
        "src/etl/config_models.py 已定義 EQUIPMENT_VALIDATION_CONSTRAINTS",
        "src/etl/config_models.py 已定義 TemporalContext 類別",
        "src/optimization/feature_alignment.py 已實作對齊驗證邏輯（E901-E903）",
        "src/equipment/equipment_validator.py 已實作並與 Cleaner 整合",
        "各模組的 ERROR_CODES 字典必須與本文件第 3 節完全一致（含新分層 E600-E999）",
    ],
    "during_development": [
        "每個檢查點必須有對應的單元測試（故意注入錯誤，驗證錯誤代碼正確）",
        "E500 檢查必須使用 Property-Based Testing（隨機生成 device_role 值，驗證絕對不會出現在輸出）",
        "E901-E903 檢查必須使用「錯誤順序特徵」測試（故意打亂特徵順序，驗證系統正確拒絕）",
        "時間基準測試（模擬長時間執行，驗證未來資料檢查使用固定基準而非動態時間）",
        "Header Standardization 測試（使用各種非標準標頭，驗證正規化邏輯）",
        "Equipment Validation Sync 測試（驗證 Cleaner 與 Optimization 的設備邏輯一致性）",
        "版本相容性矩陣必須有整合測試覆蓋（使用不同版本組合的 fixture）",
    ],
    "pre_release": [
        "執行端到端契約測試：Parser → Cleaner → BatchProcessor → FeatureEngineer → Model Training → Optimization，驗證檢查點 1-7 全部通過",
        "執行 Annotation 流程測試：Excel → Wizard → excel_to_yaml → Container，驗證檢查點 5-6 全部通過",
        "執行特徵對齊壓力測試：訓練後故意修改特徵順序，驗證 Optimization 階段正確拋出 E901",
        "執行 Header Standardization 壓力測試：使用包含空格、特殊字元、大小寫混亂的 CSV 標頭，驗證正確轉換或拋出 E105",
        "執行 Equipment Validation Sync 測試：在 Cleaner 中注入設備邏輯違規資料，驗證正確標記並傳遞至 Optimization",
        "驗證錯誤訊息：所有錯誤代碼必須輸出本文件定義的「使用者訊息範本」",
    ],
}


# =============================================================================
# 12. ETLConfig & AnnotationConfig (Pydantic Models)
# =============================================================================

from pydantic import BaseModel, Field, field_validator


class AnnotationConfig(BaseModel):
    """
    Feature Annotation 配置模型
    
    定義單一特徵欄位的標註配置。
    """
    column_name: str = Field(..., description="CSV 欄位名稱（經正規化後）")
    physical_type: str = Field(..., description="物理類型")
    unit: Optional[str] = Field(None, description="單位")
    description: str = Field("", description="欄位描述")
    device_role: Optional[str] = Field(None, description="設備角色")
    is_target: bool = Field(False, description="是否為目標變數")
    enable_lag: bool = Field(False, description="是否啟用 Lag 特徵")
    lag_intervals: List[int] = Field(default_factory=list, description="Lag 間隔列表")
    valid_range: Optional[Tuple[float, float]] = Field(None, description="有效範圍")
    precision: Optional[int] = Field(None, description="精度（小數位數）")
    
    @field_validator('physical_type')
    @classmethod
    def validate_physical_type(cls, v: str) -> str:
        allowed = FEATURE_ANNOTATION_CONSTANTS["physical_types"]
        if v not in allowed:
            raise ValueError(f"物理類型 '{v}' 不在允許列表: {allowed}")
        return v
    
    @field_validator('device_role')
    @classmethod
    def validate_device_role(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = FEATURE_ANNOTATION_CONSTANTS["device_role_values"]
        if v not in allowed:
            raise ValueError(f"設備角色 '{v}' 不在允許列表: {allowed}")
        return v
    
    @field_validator('enable_lag')
    @classmethod
    def validate_lag_config(cls, v: bool, info) -> bool:
        values = info.data
        if v and values.get('is_target'):
            raise ValueError(f"E405: 目標變數不可啟用 Lag")
        return v


class SiteFeatureConfig(BaseModel):
    """
    案場特徵配置模型
    
    對應單一案場的 feature annotation YAML 檔案。
    """
    schema_version: str = Field("1.3", description="Schema 版本")
    site_id: str = Field(..., description="案場 ID")
    inherit: Optional[str] = Field(None, description="繼承的父配置檔案")
    description: str = Field("", description="案場描述")
    
    # 同步資訊（E406 檢查用）
    excel_source: Optional[str] = Field(None, description="來源 Excel 檔案路徑")
    excel_checksum: Optional[str] = Field(None, description="Excel 檔案 SHA256")
    last_sync_timestamp: Optional[str] = Field(None, description="最後同步時間")
    quality_flags_reference: List[str] = Field(
        default_factory=list, 
        description="同步時的 VALID_QUALITY_FLAGS"
    )
    
    # 特徵定義
    features: List[AnnotationConfig] = Field(
        default_factory=list, 
        description="特徵欄位列表"
    )
    
    # HVAC 設備限制
    equipment_constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="設備限制條件（與 EQUIPMENT_VALIDATION_CONSTRAINTS 合併）"
    )


class ETLConfig(BaseModel):
    """
    ETL Pipeline 全域配置模型
    
    作為系統整合的 SSOT 配置入口，整合所有子配置。
    
    Attributes:
        version: 配置版本
        site_id: 案場 ID
        temporal_baseline: 時間基準（ISO 8601 格式）
        annotation: Feature Annotation 配置
        checkpoint_validations: 啟用的檢查點驗證
    """
    
    # 基本資訊
    version: str = Field("1.2.0", description="ETLConfig 版本")
    site_id: str = Field(..., description="案場 ID")
    pipeline_id: Optional[str] = Field(None, description="Pipeline 執行 ID")
    
    # 時間基準
    temporal_baseline: Optional[str] = Field(
        None, 
        description="Pipeline 啟動時間基準（ISO 8601 UTC）"
    )
    
    # Feature Annotation 配置
    annotation: SiteFeatureConfig = Field(
        default_factory=lambda: SiteFeatureConfig(site_id="default"),
        description="Feature Annotation 配置"
    )
    
    # 檢查點啟用設定
    checkpoint_validations: Dict[str, bool] = Field(
        default_factory=lambda: {
            "#1": True,   # Parser → Cleaner
            "#2": True,   # Cleaner → BatchProcessor
            "#3": True,   # BatchProcessor → FeatureEngineer
            "#4": True,   # FeatureEngineer → Model Training
            "#5": True,   # Excel ↔ YAML Sync
            "#6": True,   # Schema Compatibility
            "#7": True,   # Model Training → Optimization
        },
        description="啟用的檢查點驗證"
    )
    
    # 模組版本（相容性檢查用）
    module_versions: Dict[str, str] = Field(
        default_factory=lambda: {
            "parser": "v2.1",
            "cleaner": "v2.2",
            "batch_processor": "v1.3",
            "feature_engineer": "v1.3",
            "model_training": "v1.2",
            "optimization": "v1.1",
            "equipment_validation": "v1.0",
        },
        description="各模組版本"
    )
    
    # 輸出設定
    output_directory: str = Field("./output", description="輸出目錄")
    staging_directory: str = Field("./.staging", description="暫存目錄")
    
    # 效能設定
    max_memory_gb: float = Field(4.0, description="最大記憶體使用（GB）")
    enable_parallel: bool = Field(True, description="啟用平行處理")
    
    def get_annotation_for_column(self, column_name: str) -> Optional[AnnotationConfig]:
        """取得指定欄位的 Annotation 配置"""
        for feature in self.annotation.features:
            if feature.column_name == column_name:
                return feature
        return None
    
    def validate_compatibility(self) -> Tuple[bool, List[str]]:
        """
        驗證模組版本相容性
        
        Returns:
            (是否相容, 不相容訊息列表)
        """
        level, notes = check_version_compatibility(
            self.module_versions.get("parser", "v0.0"),
            self.module_versions.get("cleaner", "v0.0"),
            self.module_versions.get("batch_processor", "v0.0"),
            self.module_versions.get("feature_engineer", "v0.0"),
            self.module_versions.get("model_training", "v0.0"),
            self.module_versions.get("optimization", "v0.0"),
            self.module_versions.get("equipment_validation", "v0.0"),
        )
        
        if level == "incompatible":
            return False, [f"版本不相容: {notes}"]
        elif level == "partial":
            return True, [f"版本部分相容: {notes}"]
        return True, []


class TopologyAggregationConfig(BaseModel):
    """
    拓樸聚合配置
    
    定義如何從上游設備聚合特徵。
    """
    enabled: bool = Field(True, description="是否啟用拓樸聚合")
    target_physical_types: List[str] = Field(
        default_factory=lambda: ["temperature", "pressure", "flow_rate"],
        description="要聚合的物理類型"
    )
    aggregation_functions: List[str] = Field(
        default_factory=lambda: ["mean", "max", "min"],
        description="聚合函數列表"
    )
    missing_strategy: str = Field("skip", description="上游缺失處理策略")
    min_valid_sources: int = Field(1, description="最小有效來源數量")


class ControlDeviationConfig(BaseModel):
    """
    控制偏差配置
    
    定義如何生成控制偏差特徵。
    """
    enabled: bool = Field(True, description="是否啟用控制偏差")
    deviation_types: List[str] = Field(
        default_factory=lambda: ["basic", "absolute", "integral"],
        description="偏差類型列表"
    )
    integral_window: int = Field(96, description="積分窗口大小")
    decay_alpha: float = Field(0.3, description="指數加權平均 alpha")


class FeatureEngineeringConfig(BaseModel):
    """
    特徵工程配置模型 v1.4
    
    定義特徵工程的各項配置，包括：
    - Lag/Rolling 特徵生成
    - 拓樸聚合特徵
    - 控制偏差特徵
    - 特徵縮放
    """
    
    # 基本設定
    version: str = Field("1.4.0", description="配置版本")
    site_id: str = Field(..., description="案場 ID")
    
    # Lag 特徵設定
    lag_enabled: bool = Field(True, description="是否啟用 Lag 特徵")
    lag_intervals: List[int] = Field(
        default_factory=lambda: [1, 2, 4, 8, 16, 32],
        description="Lag 間隔列表"
    )
    
    # Rolling 特徵設定
    rolling_enabled: bool = Field(True, description="是否啟用 Rolling 特徵")
    rolling_windows: List[int] = Field(
        default_factory=lambda: [4, 16, 32, 96],
        description="Rolling 窗口列表"
    )
    rolling_functions: List[str] = Field(
        default_factory=lambda: ["mean", "std", "min", "max"],
        description="Rolling 函數列表"
    )
    
    # 差分特徵設定
    diff_enabled: bool = Field(True, description="是否啟用差分特徵")
    diff_orders: List[int] = Field(default_factory=lambda: [1], description="差分階數")
    
    # 拓樸聚合設定
    topology_aggregation: TopologyAggregationConfig = Field(
        default_factory=TopologyAggregationConfig,
        description="拓樸聚合配置"
    )
    
    # 控制偏差設定
    control_deviation: ControlDeviationConfig = Field(
        default_factory=ControlDeviationConfig,
        description="控制偏差配置"
    )
    
    # 特徵縮放設定
    scaling_enabled: bool = Field(True, description="是否啟用特徵縮放")
    scaling_method: str = Field("standard", description="縮放方法 (standard/minmax/robust)")
    
    # GNN 設定
    gnn_enabled: bool = Field(True, description="是否輸出 GNN 資料")
    gnn_output_format: str = Field("both", description="GNN 輸出格式 (static/timeline/both)")
    
    # 防 Data Leakage 設定
    strict_mode: bool = Field(True, description="嚴格模式（禁止動態計算統計值）")
    
    # 記憶體優化
    memory_optimization: bool = Field(True, description="啟用記憶體優化 (Float32)")


# =============================================================================
# 13. 模組匯出清單
# =============================================================================

__all__ = [
    # 錯誤代碼
    "ErrorSeverity",
    "ErrorCode",
    "ERROR_CODES",
    "get_error_code",
    "format_error_message",
    
    # 品質標記
    "VALID_QUALITY_FLAGS",
    "VALID_QUALITY_FLAGS_SET",
    "validate_quality_flags",
    
    # 時間戳設定
    "TIMESTAMP_CONFIG",
    
    # Feature Annotation
    "FEATURE_ANNOTATION_CONSTANTS",
    
    # Header 正規化
    "HEADER_STANDARDIZATION_RULES",
    "HeaderStandardizationError",
    "standardize_header",
    
    # 設備驗證
    "EQUIPMENT_VALIDATION_CONSTRAINTS",
    
    # 時間基準
    "TemporalContext",
    
    # 版本相容性
    "VERSION_COMPATIBILITY_MATRIX",
    "check_version_compatibility",
    
    # 檢查點
    "CHECKPOINTS",
    
    # DataFrame 介面
    "DATAFRAME_INTERFACE_STANDARD",
    
    # 檢查清單
    "IMPLEMENTATION_CHECKLIST",
    
    # Pydantic 配置模型
    "AnnotationConfig",
    "SiteFeatureConfig",
    "ETLConfig",
    "TopologyAggregationConfig",
    "ControlDeviationConfig",
    "FeatureEngineeringConfig",
]
