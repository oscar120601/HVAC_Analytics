# PRD v1.3: 批次處理器強健性重構指南 (BatchProcessor Implementation Guide)
# 整合 Feature Annotation v1.2：Metadata 傳遞與稽核軌跡

**文件版本:** v1.3-FA (Feature Annotation Alignment & Audit Trail Preservation)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**目標模組:** `src/etl/batch_processor.py` (v1.3+)  
**上游契約:** `src/etl/cleaner.py` (v2.2+, 檢查點 #2)  
**下游契約:** `src/etl/feature_engineer.py` (v1.3+, 檢查點 #3)  
**關鍵相依:** `src/features/annotation_manager.py` (v1.2+, 提供繼承鏈與版本資訊)  
**預估工時:** 5 ~ 6 個工程天（含 Annotation 稽核軌跡與整合測試）

---

## 1. 執行總綱與設計哲學

### 1.1 版本變更總覽 (v1.2 → v1.3-FA)

| 變更類別 | v1.2 狀態 | v1.3-FA 修正 | 影響層級 |
|:---|:---|:---|:---:|
| **Metadata 傳遞** | Manifest 無 `feature_metadata` | **強制包含** `feature_metadata` (不含 device_role，僅物理屬性) | 🔴 Critical |
| **Annotation 稽核軌跡** | 無版本記錄 | **新增** `annotation_audit_trail` (schema_version, checksum, inheritance_chain) | 🔴 Critical |
| **E406 檢查點** | 無同步檢查 | **新增** Excel/YAML 同步驗證 (檢查點 #5 延伸) | 🔴 Critical |
| **Data Leakage 防護** | 無未來資料檢查 | **保留** `_check_future_data()` (E205) | 🔴 Critical |
| **Parquet Schema 驗證** | 僅寫入時檢查 | **寫入後強制驗證** INT64/UTC (E206) | 🔴 Critical |
| **職責分離** | 無明確規範 | **明確**：BatchProcessor 不處理 device_role 邏輯，僅記錄 Annotation 版本資訊 | 🟡 Medium |

### 1.2 核心設計原則

1. **Metadata 零遺失，職責清晰**：接收 Cleaner 傳遞的 `column_metadata`（僅含 physical_type/unit，不含 device_role），完整寫入 Manifest，供下游 Feature Engineer 對照 Annotation SSOT
2. **稽核軌跡完整性**：Manifest 必須記錄 Feature Annotation 的 schema_version、excel_checksum、inheritance_chain，確保資料處理過程可回溯
3. **SSOT 版本鎖定**：寫入 Manifest 時記錄當前使用的 `VALID_QUALITY_FLAGS` 與 Annotation schema 快照，防止版本漂移
4. **E406 前置防護**：在 Pipeline 啟動時檢查 Excel/YAML 同步狀態（若 `enforce_annotation_sync=True`）
5. **零複製銜接**：Cleaner v2.2 輸出的 DataFrame 不含 device_role，BatchProcessor 不應添加任何 Annotation 邏輯欄位，僅傳遞版本資訊至 Manifest

---

## 2. 介面契約規範 (Interface Contracts)

### 2.1 輸入契約 (Input Contract from Cleaner v2.2)

**檢查點 #2: Cleaner → BatchProcessor**

| 檢查項 | 規範 | 容錯處理 | 錯誤代碼 |
|:---|:---|:---|:---:|
| `timestamp` | `Datetime(UTC, ns)` | 若不符，嘗試轉換或拒絕 | E201 |
| `quality_flags` | `List[str]`，值 ⊆ `VALID_QUALITY_FLAGS` | 拒絕寫入，提示更新 SSOT | E202 |
| `column_metadata` | `Dict[str, ColumnMeta]` (物理屬性) | 若缺失，使用保守預設 | E203 (Warning) |
| **device_role 欄位** | **禁止存在於 DataFrame** | 若發現，拋出 E500 (契約違反) | **E500** |
| 時間連續性 | `temporal_continuity` 標記 | 記錄於 Manifest，不阻斷處理 | - |

**關鍵約束**：
- 🔴 **輸入 DataFrame 不得包含 device_role**：Cleaner v2.2 已確保輸出不含 device_role，BatchProcessor 需驗證此契約
- 🟡 **column_metadata 僅含物理屬性**：`physical_type`, `unit`, `description`，**不得**包含 `device_role`, `ignore_warnings`

### 2.2 輸出契約 (Output Contract to Feature Engineer v1.3)

**檢查點 #3: BatchProcessor → Feature Engineer**

**Manifest 結構 (v1.3-FA 關鍵擴充)**:

```python
class Manifest(BaseModel):
    """BatchProcessor v1.3-FA Manifest 結構 (Interface Contract v1.0 #3)"""
    
    # 基礎資訊
    manifest_version: str = "1.3-FA"
    batch_id: str                    # UUID v4
    site_id: str                     # 案場識別 (如 "cgmh_ty")
    created_at: datetime             # ISO 8601 UTC
    
    # 【關鍵】Feature Metadata 傳遞 (來自 Cleaner，不含 device_role)
    feature_metadata: Dict[str, FeatureMetadata]
    # 範例: {"chiller_1_load": {"physical_type": "chiller_load", "unit": "RT"}}
    # ❌ 禁止包含: device_role, ignore_warnings (這些由 FE 直接讀取 Annotation)
    
    # 【新增】Annotation 稽核軌跡 (供回溯與版本驗證)
    annotation_audit_trail: Dict = {
        "schema_version": "1.2",
        "template_version": "1.2",
        "yaml_checksum": "sha256:abc123...",      # Excel 來源檔案雜湊
        "inheritance_chain": "base -> cgmh_ty",   # 繼承鏈資訊
        "last_updated": "2026-02-13T10:00:00",
        "editor": "王工程師"
    }
    
    # SSOT 快照 (版本相容性檢查)
    quality_flags_schema: List[str]  # 當前使用的 VALID_QUALITY_FLAGS 快照
    timestamp_schema: Dict = {        # 時間戳規範快照
        "format": "INT64",
        "unit": "nanoseconds", 
        "timezone": "UTC"
    }
    
    # 輸出檔案資訊
    output_files: List[str]          # 相對路徑列表
    output_format: str = "parquet"
    compression: str = "snappy"
    
    # 資料統計
    statistics: Dict = {
        "total_rows": int,
        "total_cols": int,
        "time_range": {"start": str, "end": str},
        "null_percent": float,
        "files_count": int
    }
    
    # 資料完整性驗證
    checksum: str                    # Manifest 本身 checksum (SHA256)
    file_checksums: Dict[str, str]   # filename → SHA256
```

**Parquet 輸出規範**:

| 欄位 | 物理型別 | 邏輯型別 | 限制 |
|:---|:---|:---|:---|
| `timestamp` | `INT64` | `Timestamp(nanoseconds, UTC)` | 禁止 INT96 |
| `quality_flags` | `BYTE_ARRAY` (JSON) | `List(Utf8)` | 以 JSON string 存儲，Polars 讀取時解析 |
| 數值欄位 | `DOUBLE` | `Float64` | - |
| **device_role** | **禁止存在** | - | **不得寫入 Parquet metadata 或 DataFrame** |

---

## 3. 分階段實作計畫 (Phase-Based Implementation)

### Phase 0: Annotation 稽核軌跡基礎建設 (Day 1, 新增)

#### Step 0.1: SSOT 嚴格引用與 AnnotationMetadata 注入

**檔案**: `src/etl/batch_processor.py` (頂部)

**實作內容**:
```python
from typing import Final, Dict, List, Optional
from pathlib import Path
import hashlib
import json
import shutil
from datetime import datetime, timezone

import polars as pl
import pyarrow.parquet as pq
from pydantic import BaseModel, validator

# 【關鍵】SSOT 嚴格引用
from src.etl.config_models import (
    VALID_QUALITY_FLAGS,      # SSOT: 6個標準品質標記
    TIMESTAMP_CONFIG,         # SSOT: UTC, ns, INT64
    FeatureMetadata,          # SSOT: 欄位元資料結構 (已移除 device_role)
    BatchConfig,             
    ETLConfig,
    FEATURE_ANNOTATION_CONSTANTS  # 【新增】Annotation 常數
)

# 【新增】Annotation 稽核軌跡
from src.features.annotation_manager import FeatureAnnotationManager

# 錯誤代碼常數 (Interface Contract v1.0)
ERROR_CODES: Final[Dict[str, str]] = {
    "E201": "SCHEMA_MISMATCH",
    "E202": "UNKNOWN_QUALITY_FLAG", 
    "E203": "METADATA_LOSS",
    "E205": "FUTURE_DATA_DETECTED",
    "E206": "PARQUET_FORMAT_VIOLATION",
    "E406": "EXCEL_YAML_OUT_OF_SYNC",  # 【新增】同步錯誤
    "E500": "DEVICE_ROLE_LEAKAGE"      # 【新增】職責違反
}
```

#### Step 0.2: 建構子與 AnnotationMetadata 注入

**檔案**: `src/etl/batch_processor.py` (`BatchOrchestrator.__init__`)

```python
class BatchOrchestrator:
    """
    BatchProcessor v1.3-FA - 整合 Feature Annotation 稽核軌跡
    
    核心職責：
    1. 接收 Cleaner 輸出（不含 device_role 的 DataFrame + column_metadata）
    2. 將 Annotation 稽核資訊（版本、checksum、繼承鏈）寫入 Manifest
    3. 執行 E406 同步檢查（若啟用）
    4. 確保輸出 Parquet 不含 device_role 欄位或 metadata
    """
    
    def __init__(
        self,
        config: ETLConfig,
        parser: ReportParser,
        cleaner: DataCleaner,
        annotation_metadata: Optional[Dict] = None  # 【新增】來自 Container 的 Annotation 資訊
    ):
        self.config = config
        self.parser = parser
        self.cleaner = cleaner
        self.annotation_metadata = annotation_metadata or {}  # 稽核軌跡資訊
        self.logger = get_logger("BatchOrchestrator")
        self.batch_id = str(uuid.uuid4())
        self.site_id = config.site_id
        
        # 【新增】E406 檢查：若啟用嚴格同步，檢查 Excel/YAML 狀態
        if config.batch.enforce_annotation_sync and annotation_metadata:
            self._validate_annotation_sync()
    
    def _validate_annotation_sync(self):
        """
        E406 檢查：確保使用的 YAML 與 Excel 同步
        此檢查在 Container 初始化時已執行，此處為二次確認
        """
        from src.utils.config_loader import ConfigLoader
        
        fa_config = self.config.feature_annotation
        sync_status = ConfigLoader.validate_annotation_sync(
            self.site_id,
            fa_config.excel_base_dir,
            fa_config.yaml_base_dir
        )
        
        if not sync_status['synced']:
            raise AnnotationSyncError(
                f"E406: {sync_status['reason']}. "
                f"請執行: python main.py features validate-annotation --site {self.site_id}"
            )
        
        self.logger.info("✅ E406: Excel/YAML 同步檢查通過")
```

---

### Phase 1: 輸入契約驗證與職責分離檢查 (Day 1, 更新)

#### Step 1.1: 輸入契約驗證（含 device_role 洩漏檢查）

**方法**: `_validate_input_contract(df: pl.DataFrame) -> None`

**詳細邏輯**:
```python
def _validate_input_contract(self, df: pl.DataFrame) -> None:
    """
    驗證 Cleaner v2.2 輸入契約 (Interface Contract #2)
    
    驗證項目:
    1. quality_flags 型別與值域
    2. timestamp 基礎檢查
    3. 【關鍵】禁止 device_role 欄位存在 (E500)
    4. 未來資料檢查 (E205)
    """
    errors = []
    
    # 1. quality_flags 驗證 (E202)
    if "quality_flags" in df.columns:
        qf_dtype = df["quality_flags"].dtype
        if not isinstance(qf_dtype, pl.List):
            errors.append(f"quality_flags 必須為 List 型別，得到 {qf_dtype}")
        else:
            actual_flags = set()
            for flags in df["quality_flags"]:
                if flags:
                    actual_flags.update(flags)
            
            invalid_flags = actual_flags - set(VALID_QUALITY_FLAGS)
            if invalid_flags:
                raise ContractViolationError(
                    f"E202: 輸入包含未定義的品質標記: {invalid_flags}。"
                )
    
    # 2. 【關鍵】職責分離檢查：禁止 device_role 欄位 (E500)
    forbidden_columns = ["device_role", "ignore_warnings", "is_target"]
    for col in forbidden_columns:
        if col in df.columns:
            errors.append(
                f"E500: 發現禁止欄位 '{col}'。Cleaner v2.2 不應將 Annotation 元資料"
                f"寫入 DataFrame，這些資訊應由 Feature Engineer 直接讀取 YAML SSOT。"
            )
    
    # 3. 未來資料檢查 (E205)
    self._check_future_data(df)
    
    if errors:
        raise ContractViolationError(f"輸入契約驗證失敗: {errors}")
    
    self.logger.debug("輸入契約驗證通過：未發現 device_role 等禁止欄位")
```

---

### Phase 2: 事務性輸出與 Parquet 寫入 (Day 2-3)

#### Step 2.1-2.3: （與原 PRD 基本一致，但強化 Schema 驗證）

**關鍵更新**：在 `_verify_parquet_schema` 中新增對 **device_role 欄位**的檢查

```python
def _verify_parquet_schema(self, file_path: Path) -> None:
    """
    驗證 Parquet 檔案符合 INT64/UTC 規範，且不含 device_role (E206/E500)
    """
    pf = pq.ParquetFile(file_path)
    schema = pf.schema
    
    # 1. 驗證 timestamp 欄位 (INT64/UTC/NANOS)
    ts_field = schema.field_by_name("timestamp")
    
    if ts_field.physical_type == "INT96":
        file_path.unlink()
        raise TypeError(f"E206: Parquet 使用已棄用的 INT96 格式")
    
    if ts_field.physical_type != "INT64":
        file_path.unlink()
        raise TypeError(f"E206: 時間戳物理型別必須為 INT64")
    
    lt = ts_field.logical_type
    if lt.type != "TIMESTAMP" or lt.unit != "NANOS" or not lt.is_adjusted_to_utc:
        file_path.unlink()
        raise TypeError(f"E206: 時間戳必須為 UTC Nanoseconds")
    
    # 2. 【新增】驗證無 device_role 欄位 (E500)
    column_names = [schema.field(i).name for i in range(schema.num_columns)]
    if "device_role" in column_names:
        file_path.unlink()
        raise ContractViolationError(
            f"E500: Parquet 檔案包含禁止欄位 'device_role'。 "
            f"BatchProcessor 不應將 device_role 寫入輸出檔案。"
        )
    
    self.logger.info(f"Schema 驗證通過: INT64/UTC/NANOS，無 device_role")
```

---

### Phase 3: Manifest 生成與 Annotation 稽核軌跡 (Day 3-4, 關鍵更新)

#### Step 3.1: Manifest 生成（含 Annotation Audit Trail）

**方法**: `_generate_manifest(df: pl.DataFrame, column_metadata: Dict, output_files: List[str]) -> Manifest`

**詳細邏輯**:
```python
def _generate_manifest(
    self, 
    df: pl.DataFrame, 
    column_metadata: Optional[Dict[str, FeatureMetadata]] = None,
    output_files: List[str] = None
) -> Manifest:
    """
    生成 Manifest (Interface Contract #3)
    
    【關鍵】整合 Annotation 稽核軌跡，但 feature_metadata 不含 device_role
    """
    # 若上游未提供 metadata，使用保守預設 (E203 Warning)
    if not column_metadata:
        self.logger.warning(
            "E203: 未接收到 column_metadata，使用保守預設 (physical_type='gauge')。 "
            "建議升級至 Cleaner v2.2+ 以傳遞完整 metadata。"
        )
        column_metadata = self._infer_metadata_conservative(df)
    
    # 【關鍵】確保 column_metadata 不含 device_role（二次防護）
    for col_name, meta in column_metadata.items():
        if hasattr(meta, 'device_role') or 'device_role' in meta:
            raise ContractViolationError(
                f"E500: column_metadata 包含 device_role。 "
                f"Cleaner 不應傳遞 device_role 至 BatchProcessor。"
            )
    
    # 計算統計資訊
    stats = {
        "total_rows": len(df),
        "total_cols": len(df.columns),
        "time_range": {
            "start": df["timestamp"].min().isoformat(),
            "end": df["timestamp"].max().isoformat()
        },
        "null_percent": df.null_count().sum() / (len(df) * len(df.columns)),
        "files_count": len(output_files)
    }
    
    # 【新增】建構 Annotation 稽核軌跡
    audit_trail = {}
    if self.annotation_metadata:
        audit_trail = {
            "schema_version": self.annotation_metadata.get('schema_version', 'unknown'),
            "template_version": self.annotation_metadata.get('template_version', 'unknown'),
            "yaml_checksum": self.annotation_metadata.get('yaml_checksum', ''),
            "inheritance_chain": self.annotation_metadata.get('inheritance_chain', 'none'),
            "last_updated": self.annotation_metadata.get('last_updated', ''),
            "editor": self.annotation_metadata.get('editor', 'unknown')
        }
    else:
        self.logger.warning("未提供 Annotation Metadata，Manifest 將缺少稽核軌跡")
    
    # 建立 Manifest
    manifest = Manifest(
        batch_id=self.batch_id,
        site_id=self.site_id,
        created_at=datetime.now(timezone.utc),
        feature_metadata=column_metadata,  # 【關鍵】僅含物理屬性，不含 device_role
        annotation_audit_trail=audit_trail,  # 【新增】稽核軌跡
        quality_flags_schema=VALID_QUALITY_FLAGS.copy(),  # SSOT 快照
        timestamp_schema={
            "format": "INT64",
            "unit": "nanoseconds",
            "timezone": "UTC"
        },
        output_files=output_files or [],
        statistics=stats,
        file_checksums=self._compute_file_checksums(output_files or [])
    )
    
    # 計算 Manifest 自身 checksum
    manifest.checksum = manifest.compute_checksum()
    
    self.logger.info(
        f"Manifest 生成完成: {self.batch_id}, "
        f"Annotation: {audit_trail.get('schema_version', 'N/A')}, "
        f"繼承鏈: {audit_trail.get('inheritance_chain', 'N/A')}"
    )
    
    return manifest
```

#### Step 3.2: 下游銜接規範（Feature Engineer 讀取方式）

**文件規範**: Feature Engineer 必須透過 Manifest 讀取，並直接查詢 Annotation SSOT 取得 device_role

```python
# Feature Engineer v1.3 的標準讀取方式
def load_from_batch_processor(manifest_path: Path) -> Tuple[pl.LazyFrame, Dict, Dict]:
    """
    從 BatchProcessor v1.3-FA 輸出讀取資料、Metadata 與稽核軌跡
    
    Returns:
        df: LazyFrame (Parquet 資料，不含 device_role)
        feature_metadata: Dict (物理屬性)
        annotation_audit_trail: Dict (版本與繼承資訊)
    """
    manifest = Manifest.parse_file(manifest_path)
    
    # 1. 驗證 Manifest 完整性
    if not manifest.validate_checksum():
        raise DataValidationError("Manifest 損毀或遭篡改")
    
    # 2. 【關鍵】驗證 SSOT 版本相容性
    if manifest.quality_flags_schema != VALID_QUALITY_FLAGS:
        logger.warning(
            f"Manifest 使用不同版本的 flags: {manifest.quality_flags_schema}"
        )
    
    # 3. 【新增】驗證 Annotation 版本
    audit = manifest.annotation_audit_trail
    if audit:
        expected_ver = FEATURE_ANNOTATION_CONSTANTS['expected_schema_version']
        if audit.get('schema_version') != expected_ver:
            raise ConfigurationError(
                f"E400: Manifest 的 Annotation 版本過舊 "
                f"({audit.get('schema_version')} vs {expected_ver})"
            )
    
    # 4. 讀取資料
    files = [manifest_path.parent / f for f in manifest.output_files]
    df = pl.scan_parquet(files)
    
    # 5. 【關鍵】Feature Engineer 直接讀取 Annotation YAML 取得 device_role
    # 而非從 manifest.feature_metadata（該處不含 device_role）
    from src.features.annotation_manager import FeatureAnnotationManager
    annotation_manager = FeatureAnnotationManager(
        site_id=manifest.site_id,
        yaml_base_dir="config/features/sites"
    )
    
    return df, manifest.feature_metadata, audit, annotation_manager
```

---

### Phase 4: 批次處理流程整合 (Day 5)

#### Step 4.1: 主處理流程（更新版）

**方法**: `process_single_file(file_path: Path) -> BatchResult`

**詳細邏輯**:
```python
@dataclass
class BatchResult:
    status: str  # "success", "failed", "future_data_rejected", "schema_invalid", "sync_error"
    file_path: Optional[Path] = None
    manifest_path: Optional[Path] = None
    error: Optional[str] = None
    annotation_audit_trail: Optional[Dict] = None  # 【新增】回傳稽核資訊

def process_single_file(self, file_path: Path) -> BatchResult:
    """
    處理單一檔案的完整流程 (含 Annotation 稽核軌跡)
    """
    try:
        # 1. 解析 (Parser v2.1)
        raw_df = self.parser.parse_file(str(file_path))
        
        # 2. 清洗 (Cleaner v2.2) - 回傳不含 device_role 的 metadata
        clean_df, column_metadata = self.cleaner.clean(raw_df)
        
        # 3. 輸入契約驗證（檢查點 #2，含 E500 device_role 檢查）
        self._validate_input_contract(clean_df)
        
        # 4. Data Leakage 檢查 (E205)
        self._check_future_data(clean_df)
        
        # 5. 設定 Staging
        staging_path = self._setup_staging()
        
        # 6. 寫入 Parquet (強制 INT64/UTC，無 device_role)
        parquet_file = self._write_parquet_atomic(clean_df, staging_path)
        
        # 7. 生成 Manifest（含 annotation_audit_trail）
        manifest = self._generate_manifest(
            clean_df, 
            column_metadata=column_metadata,
            output_files=["data.parquet"]
        )
        
        # 8. 寫入 Manifest
        manifest_path = staging_path / "manifest.json"
        manifest_path.write_text(manifest.json(indent=2))
        
        # 9. 計算檔案 checksums
        manifest.file_checksums = {
            "data.parquet": self._compute_file_hash(parquet_file)
        }
        manifest_path.write_text(manifest.json(indent=2))
        
        # 10. 原子移動至輸出目錄
        final_path = self._atomic_move_to_output(staging_path)
        
        return BatchResult(
            status="success",
            file_path=file_path,
            manifest_path=final_path / "manifest.json",
            annotation_audit_trail=manifest.annotation_audit_trail  # 【新增】
        )
        
    except AnnotationSyncError as e:  # 【新增】E406
        return BatchResult(
            status="sync_error",
            file_path=file_path,
            error=str(e)
        )
        
    except FutureDataError as e:
        return BatchResult(
            status="future_data_rejected",
            file_path=file_path,
            error=str(e)
        )
        
    except ContractViolationError as e:  # E202, E206, E500
        self.logger.error(f"契約違反 {file_path}: {e}")
        self._cleanup_staging()
        return BatchResult(
            status="schema_invalid",
            file_path=file_path,
            error=str(e)
        )
        
    except Exception as e:
        self.logger.exception(f"處理失敗 {file_path}: {e}")
        self._cleanup_staging()
        return BatchResult(
            status="failed",
            file_path=file_path,
            error=str(e)
        )
```

---

## 4. 錯誤代碼對照表 (Error Codes)

| 錯誤代碼 | 名稱 | 發生階段 | 說明 | 處理建議 |
|:---|:---|:---:|:---|:---|
| **E201** | `INPUT_SCHEMA_MISMATCH` | Step 1.1 | 輸入 DataFrame Schema 不符 | 檢查 Cleaner 輸出設定 |
| **E202** | `UNKNOWN_QUALITY_FLAG` | Step 1.1 | 輸入含未定義的 quality_flags | 同步更新 SSOT |
| **E203** | `METADATA_LOSS` | Step 3.1 | 未接收到 column_metadata | 升級至 Cleaner v2.2+ |
| **E205** | `FUTURE_DATA_DETECTED` | Step 1.1 | 資料時間超過現在+5分鐘 | 檢查資料來源時鐘 |
| **E206** | `PARQUET_FORMAT_VIOLATION` | Step 2.1 | Parquet 格式非 INT64/UTC | 檢查 use_pyarrow=False |
| **E406** | `EXCEL_YAML_OUT_OF_SYNC` | Step 0.2 | Excel 與 YAML 不同步 | 執行 validate-annotation |
| **E500** | `DEVICE_ROLE_LEAKAGE` | Step 1.1/2.1 | DataFrame 或 Metadata 含 device_role | 檢查 Cleaner 邏輯，確保職責分離 |

---

## 5. 測試與驗證計畫 (Test Plan)

### 5.1 單元測試 (Unit Tests)

| 測試案例 ID | 描述 | 輸入 | 預期結果 | 對應 Step |
|:---|:---|:---|:---|:---:|
| BP13-FA-01 | E406 同步檢查 | Excel 較新 | 拋出 AnnotationSyncError | 0.2 |
| BP13-FA-02 | device_role 攔截 | DataFrame 含 device_role 欄位 | 拋出 E500 | 1.1 |
| BP13-FA-03 | Metadata 不含 device_role | column_metadata 含 device_role | 拋出 E500 | 3.1 |
| BP13-FA-04 | 稽核軌跡完整性 | 正常處理 | Manifest 含 inheritance_chain | 3.1 |
| BP13-FA-05 | Parquet 無 device_role | 正常寫入後 | Schema 驗證通過，無禁止欄位 | 2.1 |
| BP13-001 | INT64 強制驗證 | 模擬 INT96 寫入 | 攔截並拋出 E206 | 2.1 |
| BP13-002 | 未來資料攔截 | 時間戳為明天 | 拋出 E205 | 1.1 |

### 5.2 整合測試 (Integration Tests)

| 測試案例 ID | 描述 | 上游 | 下游 | 驗證目標 |
|:---|:---|:---:|:---:|:---|
| **INT-BP-FA-01** | E406 檢查點 | Excel 修改未生成 YAML | BP v1.3 | 正確拋出 E406，阻擋處理 |
| **INT-BP-FA-02** | Cleaner 職責分離 | Cleaner v2.2 (無 device_role) | BP v1.3 | 正確接收，Manifest 無 device_role |
| **INT-BP-FA-03** | 稽核軌跡傳遞 | BP v1.3 (含 inheritance_chain) | FE v1.3 | FE 正確讀取版本與繼承資訊 |
| INT-B01 | Cleaner v2.2 → BP v1.3 | Cleaner v2.2 (UTC, metadata) | BP v1.3 | 正確接收 metadata，無 E203 |
| INT-B02 | BP v1.3 → Feature Engineer v1.3 | BP v1.3 (Manifest) | FE v1.3 | FE 正確讀取 audit_trail |

---

## 6. 風險評估與緩解 (Risk Assessment)

| 風險 | 嚴重度 | 可能性 | 緩解措施 |
|:---|:---:|:---:|:---|
| **device_role 洩漏** (Cleaner 誤寫入) | 🔴 High | Medium | E500 檢查攔截，CI/CD 測試 BP13-FA-02/03 |
| **Annotation 不同步** (E406) | 🔴 High | Medium | 啟動時強制檢查，明確錯誤訊息指引 |
| **繼承鏈遺失** | 🟡 Medium | Low | Manifest 強制記錄 inheritance_chain，驗證測試 |
| **INT96 回退** | 🔴 High | Medium | 寫入後 Schema 驗證 (E206) |
| **Metadata 遺失** | 🟡 Medium | High | Fallback 保守預設 (E203 Warning) |

---

## 7. 版本相容性矩陣 (Version Compatibility)

| Cleaner | BatchProcessor | Feature Engineer | Feature Annotation | 相容性 | 說明 |
|:---:|:---:|:---:|:---:|:---:|:---|
| v2.2 (無 device_role) | **v1.3-FA** | v1.3+ | v1.2 | ✅ **完全相容** | 推薦配置，稽核軌跡完整 |
| v2.2 | **v1.3-FA** | v1.2 | v1.2 | ⚠️ **部分相容** | FE v1.2 無法讀取 audit_trail，但功能正常 |
| v2.1 (有 device_role) | **v1.3-FA** | 任意 | v1.2 | ❌ **不相容** | 觸發 E500，需升級 Cleaner |
| 任意 | v1.2 | 任意 | v1.2 | ❌ **不相容** | v1.2 無法記錄 Annotation 稽核軌跡 |

---

## 8. 交付物清單 (Deliverables)

### 8.1 程式碼檔案
1. `src/etl/batch_processor.py` - 主要實作 (v1.3-FA，含 E406/E500 檢查與稽核軌跡)
2. `src/etl/manifest.py` - Manifest 模型更新 (新增 annotation_audit_trail)
3. `src/etl/contract_validator.py` - 契約驗證邏輯 (可複用模組)

### 8.2 測試檔案
4. `tests/test_batch_processor_v13_fa.py` - v1.3-FA 專屬測試（含 E406/E500 驗證）
5. `tests/test_manifest_audit_trail.py` - 稽核軌跡完整性測試
6. `tests/test_integration_annotation_sync.py` - E406 同步檢查整合測試

### 8.3 文件檔案
7. `docs/batch_processor/PRD_BATCH_PROCESSOR_v1.3-FA.md` - 本文件
8. `docs/batch_processor/MANIFEST_SPEC_v1.3-FA.md` - Manifest JSON Schema 規範 (供 Feature Engineer 參考)

---

## 9. 驗收簽核 (Sign-off Checklist)

- [ ] **E406 檢查**：Excel 修改時間晚於 YAML 時，正確拋出 E406 並指引執行 validate-annotation
- [ ] **職責分離 (E500)**：輸入 DataFrame 含 device_role 欄位時，正確拋出 E500
- [ ] **Metadata 純淨**：column_metadata 傳遞過程中不含 device_role，通過 Step 3.1 驗證
- [ ] **Parquet 純淨**：輸出 Parquet Schema 不含 device_role 欄位（E500 檢查）
- [ ] **稽核軌跡**：Manifest 正確記錄 `annotation_audit_trail`（含 schema_version, inheritance_chain, yaml_checksum）
- [ ] **INT64/UTC**：寫入後驗證 `physical_type == "INT64"` 且 `is_adjusted_to_utc == True`
- [ ] **SSOT 快照**：Manifest 包含 `quality_flags_schema` 與當前 SSOT 一致
- [ ] **下游銜接**：Feature Engineer v1.3 可正確讀取 `annotation_audit_trail` 並直接查詢 Annotation SSOT

---

**關鍵設計確認**：
1. BatchProcessor **不處理** device_role 邏輯（僅傳遞版本資訊）
2. Manifest 的 `feature_metadata` **僅含** physical_type/unit（來自 Cleaner）
3. Manifest 的 `annotation_audit_trail` **僅供稽核**（版本、checksum、繼承鏈）
4. Feature Engineer **直接讀取** YAML SSOT 取得 device_role（而非依賴 Manifest）