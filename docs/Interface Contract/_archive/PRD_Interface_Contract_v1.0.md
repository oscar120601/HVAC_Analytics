我將為您提供修正後的完整版 PRD_Interface_Contract_v1.0.md。此版本解決了錯誤代碼分層衝突、建立時間基準傳遞機制，並詳細定義 Training-Optimization 之間的特徵對齊契約。

```markdown
# PRD v1.0: 模組介面契約總綱 (Interface Contract Specification)

**文件版本:** v1.0-Revised (Zero-Gap Contract Definition)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**範圍:** 全 ETL Pipeline + Model Training + Optimization 模組間介面規範  
**相依文件:** 
- Parser v2.1+, Cleaner v2.2+, BatchProcessor v1.3+, FeatureEngineer v1.3+
- Feature Annotation v1.2+, Model Training v1.2+, Optimization v1.1+

---

## 1. 設計哲學與核心原則

### 1.1 契約優先 (Contract-First)
所有模組間的資料交換必須通過**靜態型別檢查**與**執行期驗證**雙重確認。契約一經定義，上游模組有義務確保輸出符合，下游模組有權利假設輸入符合，任何違反視為系統錯誤。

### 1.2 防禦性驗證 (Defensive Validation)
- **上游驗證**: 模組輸出前必須自我驗證（Self-Check），確保不傳遞「已知錯誤」
- **下游驗證**: 模組輸入時必須嚴格驗證（Strict Validation），拒絕任何不符合契約的輸入
- **容錯策略**: 寧可**終止流程**（Fail Fast），也不傳遞可疑資料

### 1.3 單一真相源 (SSOT) 引用
所有驗證邏輯必須引用 `src/etl/config_models.py` 中定義的常數：
- `VALID_QUALITY_FLAGS`: 品質標記唯一清單
- `TIMESTAMP_CONFIG`: 時間戳規格（UTC, nanoseconds, INT64）
- `FEATURE_ANNOTATION_CONSTANTS`: Feature Annotation 版本與 schema 定義
- `PIPELINE_TEMPORAL_BASELINE`: 時間基準傳遞規格（見第8章）

### 1.4 全域時間基準 (Global Temporal Baseline)
所有「未來資料檢查」與「時間相關驗證」必須使用 Pipeline 啟動時產生的**統一時間戳**（`pipeline_origin_timestamp`），而非模組執行時的動態 `datetime.now()`，以防止長時間執行流程中的時間漂移（見第8章）。

---

## 2. 檢查點規格 (Checkpoint Specifications)

### 2.1 檢查點 #1: Parser → Cleaner (Raw Data Contract)

**位置**: `src/etl/parser.py` 輸出驗證 (`_validate_output_contract`)

| 驗證項目 | 規格 | 失敗代碼 | 嚴重度 |
|:---|:---|:---:|:---:|
| **必要欄位** | 必須包含 `timestamp` | E003 | Critical |
| **時間戳型別** | `pl.Datetime(time_unit='ns', time_zone='UTC')` | E002 | Critical |
| **時間戳物理型別** | Parquet 層級必須為 `INT64` (非 INT96) | E002 | Critical |
| **時間戳時區** | `time_zone` 屬性必須等於 `"UTC"` | E002 | Critical |
| **編碼正確性** | 無 UTF-8 BOM (`\ufeff`) 殘留 | E001 | Critical |
| **Null Byte 檢查** | 字串欄位不可包含 `\x00` | E001 | Critical |
| **Quality Flags** | 若存在，值必須 ⊆ `VALID_QUALITY_FLAGS` | E003 | High |
| **數值欄位型別** | 感測器數據必須為 `pl.Float64` | E003 | High |
| **換行符號** | 統一為 `\n` (LF)，不可有 `\r` (CR) | E001 | Medium |
| **時間基準繼承** | 必須接收並傳遞 `pipeline_origin_timestamp` | E000 | Critical |

**容錯處理**:
- 時區非 UTC: 嘗試自動轉換並發出 **E101 Warning**（僅限 Parser v2.1 相容模式，v2.2+ 視為錯誤）
- 編碼非 UTF-8: 嘗試轉換，失敗則拋出 **E001 Error**

---

### 2.2 檢查點 #2: Cleaner → BatchProcessor (Clean Data Contract)

**位置**: `src/etl/cleaner.py` 輸出驗證 (`_validate_output_contract`) 與 BatchProcessor 輸入驗證 (`_validate_input_contract`)

| 驗證項目 | 規格 | 失敗代碼 | 嚴重度 |
|:---|:---|:---:|:---:|
| **時間戳連續性** | `timestamp` 必須為連續時間軸（無缺口）或明確標記 `INSUFFICIENT_DATA` | - | Info |
| **Quality Flags 型別** | `pl.List(pl.Utf8)` | E201 | Critical |
| **Quality Flags 值域** | 所有值必須 ∈ `VALID_QUALITY_FLAGS` | E202 | Critical |
| **Metadata 傳遞** | 必須提供 `column_metadata: Dict[str, FeatureMetadata]` | E203 | Warning |
| **禁止欄位檢查** | **不可包含** `device_role`, `ignore_warnings`, `is_target` | **E500** | **Critical** |
| **未來資料檢查** | 時間戳不可超過 `pipeline_origin_timestamp + 5 minutes` | E102 | High |
| **時區一致性** | 必須為 UTC (ns)，與檢查點 #1 相同 | E201 | Critical |
| **時間基準一致性** | 輸出 metadata 必須包含與輸入相同的 `pipeline_origin_timestamp` | E000 | Critical |

**關鍵約束**:
- **E500 (Device Role Leakage)**: Cleaner v2.2 絕對禁止將 `device_role` 寫入 DataFrame 或 metadata。此檢查為**零容錯**（Zero Tolerance），一旦發現立即終止流程。
- **Metadata 純淨性**: `column_metadata` 僅可包含 `physical_type`, `unit`, `description`，禁止包含 `device_role`（即使從 AnnotationManager 讀取也不得寫入）。

---

### 2.3 檢查點 #3: BatchProcessor → FeatureEngineer (Storage Contract)

**位置**: `src/etl/batch_processor.py` 輸出驗證 (`_verify_parquet_schema`) 與 FeatureEngineer 輸入驗證 (`load_from_manifest`)

**Manifest 契約**:
```python
class Manifest(BaseModel):
    manifest_version: str = "1.3-FA"
    batch_id: str                      # UUID v4
    site_id: str
    created_at: datetime               # ISO 8601 UTC
    
    # 核心資料傳遞
    feature_metadata: Dict[str, FeatureMetadata]  # 不含 device_role
    annotation_audit_trail: Dict       # 必須包含 schema_version, inheritance_chain
    
    # SSOT 快照
    quality_flags_schema: List[str]    # 當下使用的 VALID_QUALITY_FLAGS 副本
    timestamp_schema: Dict             # {format: "INT64", unit: "nanoseconds", timezone: "UTC"}
    
    # 時間基準傳遞 (新增)
    temporal_baseline: Dict            # {pipeline_origin_timestamp: str, timezone: "UTC"}
    
    # 輸出檔案
    output_files: List[str]            # 相對路徑
    output_format: str = "parquet"
    
    # 完整性驗證
    checksum: str                      # Manifest SHA256
    file_checksums: Dict[str, str]     # filename → SHA256
```

| 驗證項目 | 規格 | 失敗代碼 | 嚴重度 |
|:---|:---|:---:|:---:|
| **Manifest 完整性** | `checksum` 驗證通過 | E301 | Critical |
| **Parquet Schema** | `timestamp` 物理型別必須為 `INT64` | E206 | Critical |
| **Parquet 時區** | `timestamp` 邏輯型別必須為 `UTC` | E206 | Critical |
| **Annotation 稽核** | 必須包含 `annotation_audit_trail` | E304 | Warning |
| **SSOT 一致性** | `quality_flags_schema` 必須與當前 SSOT 相容 | E303 | High |
| **未來資料防護** | 批次時間範圍不可超過 `temporal_baseline.pipeline_origin_timestamp + 5min` | E205 | High |
| **device_role 不存在** | Parquet Schema 與 DataFrame 皆不可含此欄位 | E500 | Critical |
| **時間基準存在性** | 必須包含 `temporal_baseline` 欄位 | E000 | Critical |

---

### 2.4 檢查點 #4: FeatureEngineer → Model Training (Feature Matrix Contract)

**位置**: `src/etl/feature_engineer.py` 輸出驗證 與 `src/training/data_validator.py` 輸入驗證

| 驗證項目 | 規格 | 失敗代碼 | 嚴重度 |
|:---|:---|:---:|:---:|
| **Data Leakage 檢查** | 特徵欄位不可包含目標變數的未來資訊 | E305 | Critical |
| **Temporal Cutoff** | 若設定 `cutoff_timestamp`，所有資料時間戳必須 ≤ cutoff | E305 | Critical |
| **Lag 特徵正確性** | `shift(n)` 必須正確實作（T-1 時刻特徵對應 T-1 資料） | E305 | Critical |
| **Quality Flag One-Hot** | 若啟用 one-hot，必須包含所有 `VALID_QUALITY_FLAGS` 對應欄位 | E303 | High |
| **Metadata 傳遞** | 必須輸出 `annotation_context` 供模型訓練記錄 | - | Info |
| **特徵順序保證** | 輸出 `feature_order_manifest` 記錄欄位順序 | E601 | High |
| **特徵縮放參數** | 若執行縮放，必須輸出 `scaler_params` (JSON格式，含 mean, scale) | E602 | High |
| **時間基準傳遞** | 必須將 `pipeline_origin_timestamp` 寫入特徵矩詮 metadata | E000 | Critical |

**特徵順序保證機制**:
```python
# FeatureEngineer 輸出範例
feature_output = {
    "X_train": np.ndarray,  # 形狀 (n_samples, n_features)
    "y_train": np.ndarray,
    "feature_order_manifest": {
        "version": "1.0",
        "features": ["chiller_1_load", "chiller_2_load", "wb_temp", ...],  # 明確順序列表
        "hash": "sha256:abc123...",  # 特徵列表的雜湊
        "pipeline_origin_timestamp": "2026-02-13T10:00:00Z"
    },
    "scaler_params": {
        "type": "StandardScaler",
        "mean_": [12.5, 13.2, 25.1, ...],
        "scale_": [2.1, 2.3, 1.5, ...],
        "feature_names": ["chiller_1_load", "chiller_2_load", "wb_temp", ...]  # 對應 mean_/scale_
    }
}
```

---

### 2.5 檢查點 #5: Excel ↔ YAML 同步檢查 (Annotation Sync Contract)

**位置**: `src/utils/config_loader.py` (`validate_annotation_sync`)

| 驗證項目 | 規格 | 失敗代碼 | 嚴重度 |
|:---|:---|:---:|:---:|
| **檔案存在性** | Excel 與 YAML 必須同時存在 | E406 | High |
| **時間戳同步** | `mtime(excel) ≤ mtime(yaml)` | E406 | High |
| **Checksum 一致性** | YAML 中記錄的 `excel_checksum` 必須與實際 Excel 檔案相符 | E406 | High |
| **範本版本** | Excel 的 `template_version` 必須等於 `EXPECTED_TEMPLATE_VERSION` | E400 | Critical |

**執行時機**:
- **嚴格模式** (`strict_sync_check=True`): Container 初始化時執行，失敗則拋出 `AnnotationSyncError` 終止流程
- **寬鬆模式**: 僅記錄 Warning，允許繼續執行（僅限開發環境）

---

### 2.6 檢查點 #6: Annotation Schema 版本相容 (Schema Compatibility Contract)

**位置**: `src/features/annotation_manager.py` 初始化與 FeatureEngineer 載入時

| 驗證項目 | 規格 | 失敗代碼 | 嚴重度 |
|:---|:---|:---:|:---:|
| **Schema 版本** | `schema_version` 必須等於 `FEATURE_ANNOTATION_CONSTANTS['expected_schema_version']` | E400 | Critical |
| **繼承鏈合法性** | `inherit` 指向的父檔案必須存在，且不可造成循環繼承 | E407 | Critical |
| **繼承合併結果** | 合併後的 YAML 必須通過 Pydantic 模型驗證 | E400 | High |
| **Checksum 格式** | `yaml_checksum` 必須符合 `sha256:[hex]` 格式 | E400 | Medium |

---

### 2.7 檢查點 #7: Model Training → Optimization (Model Artifact & Feature Alignment Contract)

**位置**: `src/training/output_validator.py` 與 `src/optimization/input_validator.py`

**此檢查點為跨階段關鍵介面，確保訓練與推論的特徵一致性**：

| 驗證項目 | 規格 | 失敗代碼 | 嚴重度 |
|:---|:---|:---:|:---:|
| **模型格式** | 必須為 `.joblib` 或 `.onnx`，且包含 `feature_order_manifest` | E701 | Critical |
| **特徵順序比對** | Optimization 輸入特徵順序必須與 Training `feature_order_manifest` 完全一致 | **E901** | **Critical** |
| **特徵數量一致性** | 輸入特徵維度必須等於模型訓練時的維度 | E902 | Critical |
| **縮放參數存在性** | 若模型使用 StandardScaler，必須存在 `scaler_params` | E903 | Critical |
| **縮放參數對齊** | `scaler_params.feature_names` 順序必須與 `feature_order_manifest.features` 一致 | E903 | Critical |
| **特徵雜湊驗證** | 可選：計算輸入特徵列表的雜湊，比對 `feature_order_manifest.hash` | E901 | High |
| **時間基準隔離** | Optimization 必須產生新的 `pipeline_origin_timestamp`，不可沿用 Training 的時間戳 | E000 | Warning |

**特徵對齊驗證詳細流程**:
```python
# 在 Optimization 初始化時執行
def validate_feature_alignment(model_artifact, input_features):
    """
    嚴格比對訓練與推論的特徵一致性
    """
    # 1. 載入訓練時的特徵清單
    training_features = model_artifact['feature_order_manifest']['features']
    
    # 2. 比對長度
    if len(input_features) != len(training_features):
        raise FeatureAlignmentError(E902, 
            f"特徵維度不匹配: 訓練時 {len(training_features)} 維，輸入 {len(input_features)} 維")
    
    # 3. 比對順序與名稱（逐個比對）
    for i, (train_feat, input_feat) in enumerate(zip(training_features, input_features)):
        if train_feat != input_feat:
            raise FeatureAlignmentError(E901,
                f"特徵錯位於索引 {i}: 訓練時為 '{train_feat}'，輸入為 '{input_feat}'")
    
    # 4. 驗證縮放參數（若存在）
    if 'scaler_params' in model_artifact:
        scaler_features = model_artifact['scaler_params']['feature_names']
        if scaler_features != training_features:
            raise FeatureAlignmentError(E903,
                "縮放參數特徵順序與訓練特徵順序不一致，可能導致縮放錯位")
    
    return True
```

---

## 3. 錯誤代碼分層規範 (Error Code Hierarchy Specification)

### 3.0 分層架構總覽

為確保全系統錯誤代碼的唯一性與可追蹤性，定義以下分層架構：

| 代碼範圍 | 層級 | 說明 |
|:---:|:---:|:---|
| **E000** | 全域 | Pipeline 時間基準相關錯誤 |
| **E001-E099** | 系統層級 | 編碼、記憶體、檔案系統、配置檔錯誤 |
| **E100-E199** | Parser | CSV/原始資料解析錯誤 |
| **E200-E299** | Cleaner | 資料清洗與驗證錯誤 |
| **E300-E349** | BatchProcessor | 批次處理與 Parquet 儲存錯誤 |
| **E350-E399** | Equipment Validation | 設備相依性與物理邏輯驗證錯誤 |
| **E400-E499** | Feature Annotation | 特徵標註與設定檔錯誤 |
| **E500-E599** | Governance | 架構違規、職責分離與安全性錯誤 |
| **E600-E699** | Feature Engineer | 特徵工程與矩陣建構錯誤 |
| **E700-E749** | Model Training | 模型訓練與驗證錯誤 |
| **E750-E799** | Hybrid Consistency | 混合模型一致性驗證錯誤 |
| **E800-E899** | Optimization | 最佳化與推論錯誤 |
| **E900-E999** | 跨階段整合 | 特徵對齊、版本相容性錯誤 |

**遷移對照表**（舊代碼 → 新代碼）：
- `E305` (Data Leakage) 保持不變（仍在 E3xx 範圍，但邏輯上屬於 Feature Engineer 階段）
- `E601-E602` (Feature Engineer 新增) 歸類於 E6xx
- `E701+` (Model Training) 歸類於 E7xx
- `E801+` (Optimization) 歸類於 E8xx（與舊 Training E801 區隔）
- `E901+` (跨階段對齊) 歸類於 E9xx

---

### 3.1 全域時間基準錯誤 (E000)

| 代碼 | 名稱 | 來源模組 | 說明 | 使用者訊息範本 | 可恢復性 |
|:---:|:---|:---:|:---|:---|:---:|
| **E000** | `TEMPORAL_BASELINE_MISSING` | Container/任意 | pipeline_origin_timestamp 未傳遞或遺失 | "時間基準遺失: 無法執行時間相關驗證" | ❌ 否 |

---

### 3.2 系統層級錯誤 (E001-E099)

| 代碼 | 名稱 | 來源模組 | 說明 | 使用者訊息範本 | 可恢復性 |
|:---:|:---|:---:|:---|:---|:---:|
| **E001** | `ENCODING_MISMATCH` | Parser | 檔案編碼無法偵測或輸出含非法字元 (BOM) | "檔案編碼錯誤: 無法識別編碼或包含 BOM 殘留" | ❌ 否 |
| **E000** | `TEMPORAL_BASELINE_MISSING` | PipelineContext | 全域時間基準未初始化 | "系統錯誤: 時間基準遺失" | ❌ 否 |
| **E006** | `MEMORY_LIMIT_EXCEEDED` | 任意 | 記憶體使用超過配置上限 | "記憶體不足: 已超過 {limit}GB 上限" | ❌ 否 |
| **E007** | `CONFIG_FILE_CORRUPTED` | ConfigLoader | YAML/JSON 設定檔解析失敗 | "設定檔損毀: {filepath}" | ❌ 否 |

---

### 3.3 ETL 處理錯誤 (E100-E399)

### 3.3 ETL Parser 錯誤 (E100-E199)

| 代碼 | 名稱 | 來源模組 | 說明 | Dtype | 可恢復性 |
|:---:|:---|:---:|:---|:---:|:---:|
| **E101** | `ENCODING_MISMATCH` | Parser | 無法偵測檔案編碼或含BOM | - | ❌ 否 |
| **E102** | `TIMEZONE_VIOLATION` | Parser | 時區非 UTC 或精度錯誤 | - | ❌ 否 |
| **E103** | `CONTRACT_VIOLATION` | Parser | 缺少必要欄位或 Quality Flags 未定義 | - | ❌ 否 |
| **E104** | `HEADER_NOT_FOUND` | Parser | 無法定位標頭行 (掃描 > 500行) | - | ❌ 否 |
| **E105** | `COLUMN_VALIDATION` | Parser | 欄位正規化失敗或數值轉型失敗 | - | ❌ 否 |
| **E111** | `TIMEZONE_WARNING` | Parser | 時區轉換警告 (非致命) | - | ✅ 是 |
| **E112** | `FUTURE_DATA_DETECTED` | Parser | 發現未來資料 (相對於 pipeline_timestamp) | Datetime | ⚠️ 部分 |

**Cleaner/BatchProcessor 階段 (E200-E299)**：

| 代碼 | 名稱 | 來源模組 | 說明 | 使用者訊息範本 | 可恢復性 |
|:---:|:---|:---:|:---|:---|:---:|
| **E201** | `INPUT_SCHEMA_MISMATCH` | BatchProcessor | 輸入 DataFrame Schema 不符 | "輸入資料格式不符: {detail}" | ❌ 否 |
| **E202** | `UNKNOWN_QUALITY_FLAG` | BatchProcessor | 輸入含未定義的品質標記 | "品質標記未定義於 SSOT: {flags}" | ❌ 否 |
| **E203** | `METADATA_LOSS` | BatchProcessor | 未接收到 column_metadata | "缺少欄位元資料，使用保守預設" | ✅ 是 |
| **E205** | `FUTURE_DATA_IN_BATCH` | BatchProcessor | 批次資料包含超過 `pipeline_origin_timestamp + 5min` 的時間戳 | "批次含未來資料，已拒絕" | ❌ 否 |
| **E206** | `PARQUET_FORMAT_VIOLATION` | BatchProcessor | Parquet 格式非 INT64/UTC | "Parquet 格式錯誤: {detail}" | ❌ 否 |

**BatchProcessor 儲存階段 (E300-E399)**：

| 代碼 | 名稱 | 來源模組 | 說明 | 使用者訊息範本 | 可恢復性 |
|:---:|:---|:---:|:---|:---|:---:|
| **E301** | `MANIFEST_INTEGRITY_FAILED` | FeatureEngineer | Manifest checksum 驗證失敗 | "Manifest 檔案損毀或遭篡改" | ❌ 否 |
| **E302** | `SCHEMA_MISMATCH` | FeatureEngineer | Parquet Schema 非 INT64/UTC | "輸入 Parquet 格式不符" | ❌ 否 |
| **E303** | `UNKNOWN_QUALITY_FLAG` | FeatureEngineer | Manifest 的 flags 與 SSOT 不符 | "Flags 版本不符: {detail}" | ⚠️ 部分 |
| **E304** | `METADATA_MISSING` | FeatureEngineer | Manifest 無 feature_metadata | "缺少特徵元資料" | ✅ 是 |
| **E305** | `DATA_LEAKAGE_DETECTED` | FeatureEngineer | 包含未來資料或目標變數洩漏 | "資料洩漏風險: {detail}" | ❌ 否 |

**Equipment Validation 階段 (E350-E399)**：

| 代碼 | 名稱 | 來源模組 | 說明 | 可恢復性 |
|:---:|:---|:---:|:---|:---:|
| **E350** | `CONSTRAINT_CONFIG_ERROR` | ValidationManager | 依賴約束設定檔解析失敗 | ❌ 否 |
| **E351** | `REQUIRES_VIOLATION` | EquipmentValidator | 違反「必須同時開啟」約束 | ⚠️ 部分 |
| **E352** | `MUTEX_VIOLATION` | EquipmentValidator | 違反「互斥」約束 | ⚠️ 部分 |
| **E353** | `SEQUENCE_VIOLATION` | EquipmentValidator | 違反開關機順序約束 | ⚠️ 部分 |
| **E354** | `MIN_RUNTIME_VIOLATION` | EquipmentValidator | 違反最小運轉時間限制 | ⚠️ 部分 |
| **E355** | `MIN_DOWNTIME_VIOLATION` | EquipmentValidator | 違反最小停機時間限制 | ⚠️ 部分 |

---

### 3.4 Feature Annotation 錯誤 (E400-E499)

| 代碼 | 名稱 | 來源模組 | 說明 | 使用者訊息範本 | 可恢復性 |
|:---:|:---|:---:|:---|:---|:---:|
| **E400** | `ANNOTATION_VERSION_MISMATCH` | ConfigLoader/FE | Schema 版本不符或範本過舊 | "Feature Annotation 版本過舊: 請執行 migrate-excel" | ❌ 否 |
| **E401** | `ORPHAN_COLUMN` | excel_to_yaml | 標註欄位不存在於資料 | "標註欄位 {col} 不存在於 CSV" | ✅ 是 |
| **E402** | `UNANNOTATED_COLUMN` | ConfigLoader/Cleaner | 資料欄位未定義於 Annotation | "未定義欄位: {col}，請執行 features wizard" | ❌ 否 |
| **E403** | `UNIT_INCOMPATIBLE` | excel_to_yaml | 單位與物理類型不匹配 | "單位錯誤: {unit} 不適用於 {physical_type}" | ❌ 否 |
| **E404** | `LAG_FORMAT_INVALID` | excel_to_yaml | Lag 間隔格式錯誤 | "Lag 格式錯誤: 必須為逗號分隔整數" | ❌ 否 |
| **E405** | `TARGET_LEAKAGE_RISK` | Pydantic Validation | is_target=True 但 enable_lag=True | "目標變數不可啟用 Lag" | ❌ 否 |
| **E406** | `EXCEL_YAML_OUT_OF_SYNC` | ConfigLoader | Excel 與 YAML 不同步 | "設定不同步: 請執行 validate-annotation" | ❌ 否 |
| **E407** | `CIRCULAR_INHERITANCE` | AnnotationManager | YAML 繼承循環 | "繼承循環偵測: {chain}" | ❌ 否 |

---

### 3.5 Governance & Architecture Violations (E500-E599)

| 代碼 | 名稱 | 來源模組 | 說明 | 使用者訊息範本 | 可恢復性 |
|:---:|:---|:---:|:---|:---|:---:|
| **E500** | `DEVICE_ROLE_LEAKAGE` | Cleaner/BatchProcessor/FE | DataFrame 或 Metadata 含 device_role | "職責違反: device_role 不應出現在 DataFrame" | ❌ 否 |
| **E501** | `DIRECT_WRITE_ATTEMPT` | Wizard | 試圖直接修改 YAML 檔案 | "安全性違反: 禁止直接寫入 YAML，請使用 Excel" | ❌ 否 |

---

### 3.6 Feature Engineer 錯誤 (E600-E699)

| 代碼 | 名稱 | 來源模組 | 說明 | 使用者訊息範本 | 可恢復性 |
|:---:|:---|:---:|:---|:---|:---:|
| **E601** | `FEATURE_ORDER_NOT_RECORDED` | FeatureEngineer | 未輸出 feature_order_manifest | "特徵順序未記錄: 無法保證推論一致性" | ❌ 否 |
| **E602** | `SCALER_PARAMS_MISSING` | FeatureEngineer | 執行縮放但未輸出縮放參數 | "縮放參數遺失: 推論階段將無法一致縮放" | ❌ 否 |
| **E603** | `FEATURE_MATRIX_SHAPE_ERROR` | FeatureEngineer | 特徵矩陣維度異常（如樣本數=0） | "特徵矩陣形狀錯誤: {shape}" | ❌ 否 |
| **E604** | `INVALID_LAG_CONFIGURATION` | FeatureEngineer | Lag 設定導致資料長度不足 | "Lag 設定錯誤: 資料長度 {n} 小於最大 Lag {lag}" | ⚠️ 部分 |

---

### 3.7 Model Training 錯誤 (E700-E749)

| 代碼 | 名稱 | 來源模組 | 說明 | 使用者訊息範本 | 可恢復性 |
|:---:|:---|:---:|:---|:---|:---:|
| **E701** | `TRAINING_MEMORY_ERROR` | ModelTrainer | GPU/CPU 記憶體不足 | "訓練記憶體不足: {detail}" | ❌ 否 |
| **E702** | `VALIDATION_FAILURE` | ModelValidator | 驗證集性能低於門檻 | "模型驗證失敗: MAPE {mape}% > 門檻 {threshold}%" | ❌ 否 |
| **E703** | `HYPERPARAMETER_INVALID` | ModelTrainer | 超參數組合無效 | "無效超參數: {param}={value}" | ❌ 否 |
| **E704** | `CHECKPOINT_SAVE_FAILED` | ModelTrainer | 模型檢查點儲存失敗 | "模型儲存失敗: {filepath}" | ⚠️ 部分 |
| **E705** | `CROSS_VALIDATION_ERROR` | ModelValidator | 交叉驗證執行失敗 | "交叉驗證錯誤: {detail}" | ❌ 否 |
| **E706** | `MODEL_ARTIFACT_CORRUPTED` | ModelValidator | 輸出模型檔案損毀或不完整 | "模型產物損毀" | ❌ 否 |

---

### 3.8 Hybrid Model Consistency (E750-E799)

| 代碼 | 名稱 | 來源模組 | 說明 | 可恢復性 |
|:---:|:---|:---:|:---|:---:|
| **E750** | `GOLDEN_DATASET_UNAVAILABLE` | ConsistentValidator | 無可用的測試集或驗證集 | ❌ 否 |
| **E751** | `DYNAMIC_TOLERANCE_EXCEEDED` | ConsistentValidator | 預測誤差超過動態容許值 | ❌ 否 |
| **E752** | `SYSTEMATIC_BIAS_DETECTED` | ConsistentValidator | 偵測到系統性偏差 (Bias > 5%) | ❌ 否 |
| **E753** | `TREND_MISMATCH` | ConsistentValidator | 趨勢方向與物理邏輯不符 (Corr < 0.95) | ❌ 否 |
| **E754** | `OUTLIER_VIOLATION` | ConsistentValidator | 存在極端異常值 (> 50kW) | ❌ 否 |
| **E755** | `INSUFFICIENT_COMPONENTS` | ConsistentValidator | L1等級（僅單一Component）無法驗證 | ❌ 否 |
| **E756** | `PARTIAL_COMPONENTS_L2` | ConsistentValidator | 僅使用L2等級（部分Components）驗證 | ⚠️ 部分 |
| **E757** | `LIGHT_LOAD_HIGH_VARIANCE` | ConsistentValidator | 輕載區間誤差較高（正常現象） | ✅ 是 |
| **E758** | `COPULA_EFFECT_DETECTED` | ConsistentValidator | 偵測到顯著耦合效應 | ✅ 是 |
| **E759** | `DATASET_QUALITY_WARNING` | ConsistentValidator | 使用驗證集或合併資料集 | ⚠️ 部分 |

---

### 3.9 Optimization 錯誤 (E800-E899)

| 代碼 | 名稱 | 來源模組 | 說明 | 使用者訊息範本 | 可恢復性 |
|:---:|:---|:---:|:---|:---|:---:|
| **E801** | `MODEL_LOAD_FAILED` | OptimizationEngine | 無法載入模型檔案 | "模型載入失敗: {model_path}" | ❌ 否 |
| **E802** | `CONSTRAINT_VIOLATION` | OptimizationEngine | 設備邏輯約束無法滿足 | "約束違反: {constraint_detail}" | ⚠️ 部分 |
| **E803** | `OPTIMIZATION_DIVERGENCE` | OptimizationEngine | 求解器無法收斂 | "最佳化發散: {solver_status}" | ⚠️ 部分 |
| **E804** | `BOUND_INFEASIBILITY` | OptimizationEngine | 變數邊界設定導致無解 | "邊界不可行: {variable}" | ❌ 否 |
| **E805** | `FORECAST_HORIZON_MISMATCH` | OptimizationEngine | 預測時程與最佳化時程不匹配 | "預測時程錯誤: 需 {required} 步，得 {actual} 步" | ❌ 否 |
| **E806** | `SYSTEM_MODEL_DISCREPANCY` | OptimizationEngine | System Model 與 Component Models 加總差異 > 5% | "模型不一致: 系統級與元件級預測差異 {diff}%" | ⚠️ 部分 |
| **E807** | `EQUIPMENT_STATE_INVALID` | OptimizationEngine | 設備狀態違反物理邏輯（如主機開但水泵關） | "設備狀態無效: {equipment_logic}" | ❌ 否 |
| **E808** | `WEATHER_DATA_MISSING` | OptimizationEngine | 缺少未來天氣預測資料 | "天氣資料缺失: 無法執行未來 {hours} 小時最佳化" | ❌ 否 |

---

### 3.10 跨階段整合錯誤 (E900-E999)

**Training-Optimization 特徵對齊錯誤**：

| 代碼 | 名稱 | 來源模組 | 說明 | 使用者訊息範本 | 可恢復性 |
|:---:|:---|:---:|:---|:---|:---:|
| **E901** | `FEATURE_ALIGNMENT_MISMATCH` | Optimization | 推論特徵順序/名稱與訓練時不一致 | "特徵對齊錯誤: 索引 {index} 預期 '{expected}'，實際 '{actual}'" | ❌ 否 |
| **E902** | `FEATURE_DIMENSION_MISMATCH` | Optimization | 推論特徵維度與訓練時不同 | "特徵維度錯誤: 訓練 {train_dim} 維，輸入 {input_dim} 維" | ❌ 否 |
| **E903** | `SCALER_MISMATCH` | Optimization | 縮放參數與特徵不匹配或缺失 | "縮放參數錯誤: {detail}" | ❌ 否 |
| **E904** | `MODEL_VERSION_INCOMPATIBLE` | Optimization | 模型版本與 Optimization 引擎不相容 | "模型版本不相容: 模型 v{model_ver}，引擎需 >= {engine_ver}" | ❌ 否 |
| **E905** | `PIPELINE_VERSION_DRIFT` | Container | 跨模組版本組合未通過相容性矩陣驗證 | "版本漂移: {module_a} v{ver_a} 與 {module_b} v{ver_b} 不相容" | ⚠️ 部分 |

---

## 4. DataFrame 介面標準 (DataFrame Interface Standard)

### 4.1 欄位命名與型別規範

**標準時間戳欄位**:
- **名稱**: `timestamp`（強制小寫，不可使用 `time`, `date`, `datetime`）
- **Polars 型別**: `pl.Datetime(time_unit='ns', time_zone='UTC')`
- **Parquet 物理型別**: `INT64` (nanoseconds since epoch, UTC)
- **禁止**: `INT96`, `microseconds`, `milliseconds`, 無時區 (naive)

**品質標記欄位**:
- **名稱**: `quality_flags`
- **Polars 型別**: `pl.List(pl.Utf8)`
- **值域**: 必須是 `VALID_QUALITY_FLAGS` 的子集
- **Parquet 儲存**: 以 JSON string 儲存，`BYTE_ARRAY` 邏輯型別

**數值欄位（感測器資料）**:
- **Polars 型別**: `pl.Float64`（統一使用 Float64，即使原始資料為整數）
- **單位**: 必須為 SI 單位（如 `kW`, `°C`, `LPM`），**禁止**在欄位名稱中編碼單位（如 `temp_c`, `power_kw`）
- **Null 值**: 使用 Polars `null`（非 `NaN` 或 magic number）
- **精度保留**: 單位轉換後必須保留至少 **6 位有效數字**（避免 0.1°C 精度損失影響 HVAC 決策）

**禁止欄位（絕對禁止出現在 DataFrame 中）**:
- `device_role`: 必須由 FeatureAnnotationManager 動態查詢，不得寫入資料
- `ignore_warnings`: 同上
- `is_target`: 同上
- `__index_level_0__`: Pandas 殘留索引，必須移除

### 4.2 Metadata 字典規範 (column_metadata)

**允許的鍵值**:
```python
{
    "column_name": str,           # 欄位名稱（與 DataFrame 欄位一致）
    "physical_type": str,         # 必須是 PHYSICAL_TYPES 的 key
    "unit": Optional[str],        # 單位符號
    "description": Optional[str],  # 人類可讀描述
    "precision": int,             # 有效數字位數（預設 6）
    "temporal_baseline": str      # ISO 8601 格式時間戳（傳遞用）
}
```

**禁止的鍵值**:
- `device_role`
- `ignore_warnings`
- `is_target`
- `valid_range`（應從 Annotation 查詢，非 metadata）

---

## 5. 版本相容性判定標準 (Version Compatibility Matrix)

### 5.1 相容性等級定義

| 等級 | 定義 | 行為 | 標示 |
|:---:|:---|:---|:---:|
| **完全相容** (Full Compatible) | 上下游模組版本組合通過所有檢查點，無需轉換或降級 | 正常執行，無警告 | 🟢 |
| **部分相容** (Partial Compatible) | 上游輸出可被下游讀取，但部分功能降級（如缺少 audit_trail） | 執行，但記錄 Warning | 🟡 |
| **不相容** (Incompatible) | 上游輸出無法通過下游檢查點，或資料語意不一致 | 拒絕執行，拋出錯誤 | 🔴 |

### 5.2 模組版本相容性矩陣

| Parser | Cleaner | BatchProcessor | Feature Engineer | Model Training | Optimization | 相容性 | 說明 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| v2.1 | v2.2 | v1.3 | v1.3 | v1.2 | v1.1 | 🟢 **完全相容** | 推薦配置，支援特徵對齊驗證 E901-E903 |
| v2.1 | v2.2 | v1.3 | v1.3 | v1.2 | v1.0 | 🔴 **不相容** | Optimization v1.0 缺少特徵對齊檢查點 #7 |
| v2.1 | v2.2 | v1.3 | v1.2 | v1.2 | v1.1 | 🟡 **部分相容** | FE v1.2 無法輸出 feature_order_manifest，觸發 E601 |
| v2.1 | v2.2 | v1.3 | v1.3 | v1.1 | v1.1 | 🟡 **部分相容** | Training v1.1 未輸出 scaler_params，Optimization 使用預設值 |
| 任意 | 任意 | 任意 | 任意 | v1.2 | v1.1 | 🔴 **不相容** | 若 Model 未包含 feature_order_manifest，觸發 E901 |

### 5.3 強制升級路徑

**不允許的組合**（系統必須拒絕啟動）：
1. Parser/Cleaner v2.0 + 任意下游（時區/職責分離衝突）
2. Feature Engineer v1.2 + Optimization v1.1（缺少特徵對齊機制，E901 無法通過）
3. Model Training v1.1 + Optimization v1.1（缺少標準化 scaler_params，E903 風險）

**建議升級順序**：
```
Feature Annotation v1.2 (基礎設施)
    ↓
Parser v2.1 (上游輸出標準化)
    ↓
Cleaner v2.2 (職責分離實作)
    ↓
BatchProcessor v1.3 (時間基準傳遞)
    ↓
FeatureEngineer v1.3 (特徵順序保證 E601)
    ↓
Model Training v1.2 (縮放參數輸出 E602)
    ↓
Optimization v1.1 (特徵對齊驗證 E901-E903)
```

---

## 6. 實作檢查清單 (Implementation Checklist)

### 6.1 開發前必須確認
- [ ] 所有模組 PRD 引用本文件作為「檢查點」與「錯誤代碼」的 SSOT
- [ ] `src/etl/config_models.py` 已定義 `VALID_QUALITY_FLAGS`, `TIMESTAMP_CONFIG`, `FEATURE_ANNOTATION_CONSTANTS`
- [ ] **新增**: `src/core/temporal_baseline.py` 已實作 `PipelineTemporalBaseline` 類別（見第8章）
- [ ] **新增**: `src/optimization/feature_alignment.py` 已實作對齊驗證邏輯（E901-E903）
- [ ] 各模組的 `ERROR_CODES` 字典必須與本文件第 3 節完全一致（含新分層 E600-E999）

### 6.2 開發中驗證
- [ ] 每個檢查點必須有對應的單元測試（故意注入錯誤，驗證錯誤代碼正確）
- [ ] E500 檢查必須使用 Property-Based Testing（隨機生成 device_role 值，驗證絕對不會出現在輸出）
- [ ] **新增**: E901-E903 檢查必須使用「錯誤順序特徵」測試（故意打亂特徵順序，驗證系統正確拒絕）
- [ ] **新增**: 時間基準測試（模擬長時間執行，驗證未來資料檢查使用固定基準而非動態時間）
- [ ] 版本相容性矩陣必須有整合測試覆蓋（使用不同版本組合的 fixture）

### 6.3 上線前驗收
- [ ] 執行端到端契約測試：Parser → Cleaner → BatchProcessor → FeatureEngineer → Model Training → Optimization，驗證檢查點 1-7 全部通過
- [ ] 執行 Annotation 流程測試：Excel → Wizard → excel_to_yaml → Container，驗證檢查點 5-6 全部通過
- [ ] **新增**: 執行特徵對齊壓力測試：訓練後故意修改特徵順序，驗證 Optimization 階段正確拋出 E901
- [ ] 驗證錯誤訊息：所有錯誤代碼必須輸出本文件定義的「使用者訊息範本」

---

## 7. 附錄：術語對照表

| 術語 | 定義 |
|:---|:---|
| **SSOT** (Single Source of Truth) | 單一真相源，指 `config_models.py` 中定義的常數與型別 |
| **Checkpoint** | 模組間的介面驗證點，資料通過時必須符合的規格 |
| **Device Role** | 設備角色（primary/backup/seasonal），定義於 Feature Annotation，**不得**寫入 DataFrame |
| **Audit Trail** | 稽核軌跡，記錄資料處理過程中的版本、繼承鏈、checksum 等資訊 |
| **Manifest** | BatchProcessor 輸出的 JSON 檔案，記錄批次處理的元資料與檔案清單 |
| **Leakage** (E500) | 職責違反，指 device_role 等 Annotation 元資料意外寫入 DataFrame |
| **Feature Order Manifest** | 記錄特徵欄位順序與雜湊的結構，確保 Training 與 Optimization 階段特徵順序一致 |
| **Temporal Baseline** | Pipeline 啟動時的統一時間戳，所有未來資料檢查的基準 |

---

## 8. Pipeline 時間基準傳遞規範 (Temporal Baseline Propagation)

### 8.1 核心機制

為解決「Pipeline 執行期間時間漂移導致未來資料誤判」問題（原 E102/E205 風險），建立以下機制：

**時間基準產生**：
- **時機**: `Container.__init__` 初始化時（第一個動作，早於任何模組初始化）
- **格式**: ISO 8601 UTC (e.g., `2026-02-13T10:00:00.000000000Z`)
- **儲存**: `TemporalContext` 物件（Thread-safe Singleton）

```python
class TemporalContext:
    """
    全域時間基準容器（單例模式）
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.origin_timestamp = datetime.now(UTC)
        return cls._instance
    
    def get_baseline(self) -> datetime:
        """取得 Pipeline 啟動時間戳"""
        return self.origin_timestamp
    
    def is_future(self, timestamp: datetime, tolerance_minutes: int = 5) -> bool:
        """
        判斷時間戳是否為「未來資料」
        標準：timestamp > origin_timestamp + tolerance_minutes
        """
        threshold = self.origin_timestamp + timedelta(minutes=tolerance_minutes)
        return timestamp > threshold
```

**傳遞機制**：
1. **Container → 各模組**: 通過建構子注入 `temporal_context: TemporalContext`
2. **模組間傳遞**: 通過 DataFrame metadata 或 Manifest 欄位 `temporal_baseline`
3. **檢查點驗證**: 每個檢查點驗證輸入資料的 `temporal_baseline` 與當前 Context 一致（防止跨 Pipeline 混用）

### 8.2 各模組實作規範

**Parser**:
- 接收 `TemporalContext`，在輸出 metadata 中記錄 `pipeline_origin_timestamp`
- 驗證邏輯：若輸入資料時間 > `context.get_baseline() + 5min`，拋出 E102

**Cleaner**:
- 從輸入 metadata 讀取 `pipeline_origin_timestamp`，傳遞至輸出
- 驗證邏輯：清洗後資料時間不可超過基準+5分鐘（E102）

**BatchProcessor**:
- 將 `temporal_baseline` 寫入 Manifest（見 2.3 節 Manifest 契約）
- 批次驗證：整個批次時間範圍不可超過基準+5分鐘（E205）

**FeatureEngineer → Model Training**:
- 特徵矩陣 metadata 必須包含 `pipeline_origin_timestamp`（用於追溯）
- **注意**: Training 階段不直接使用此時間戳進行「未來檢查」，但必須傳遞至模型產物

**Optimization**:
- **產生新基準**: Optimization 階段必須產生新的 `pipeline_origin_timestamp`（推論當下時間）
- **不可沿用 Training 時間**: 防止「訓練時的未來資料」在推論時變成「過去資料」的邏輯錯誤

### 8.3 錯誤處理

| 場景 | 錯誤代碼 | 處理方式 |
|:---|:---:|:---|
| Container 未初始化 TemporalContext | E000 | 立即終止，記錄「時間基準未建立」 |
| 模組接收不到 temporal_baseline | E000 | 終止流程，要求檢查上游輸出 |
| 時間戳格式非 ISO 8601 UTC | E002 | 視為時區違反 |
| 基準時間與系統時間差距過大（>1小時） | E000-Warning | 警告「Pipeline 執行時間過長或系統時間異常」 |

---

## 9. 特徵對齊與縮放參數傳遞規範 (Feature Alignment & Scaling Contract)

### 9.1 問題定義

為解決「Training 與 Optimization 特徵向量不一致導致 Silent Failure」風險（原第3點建議），建立以下嚴格契約：

**風險場景**：
- Training: 特徵順序 `[chiller_1_load, chiller_2_load, wb_temp, ...]`
- Optimization: 特徵順序 `[wb_temp, chiller_1_load, chiller_2_load, ...]`
- 結果：模型將 `wb_temp` 誤認為 `chiller_2_load`，導致預測完全錯誤但無警告

### 9.2 Feature Manifest 規格

**輸出位置**: `ModelTrainer` 輸出目錄中的 `feature_manifest.json`

```json
{
  "manifest_version": "2.0-ALIGN",
  "created_at": "2026-02-13T10:30:00Z",
  "pipeline_origin_timestamp": "2026-02-13T10:00:00Z",
  
  "feature_specification": {
    "feature_names": ["chiller_1_load", "chiller_2_load", "wb_temp", "chwst_temp"],
    "feature_count": 4,
    "feature_hash": "sha256:a1b2c3d4...",
    "hash_algorithm": "SHA256",
    "hash_computation": "sha256(','.join(feature_names).encode())"
  },
  
  "scaling_specification": {
    "scaler_type": "StandardScaler",
    "scaler_params": {
      "mean_": [450.5, 420.3, 28.5, 7.2],
      "scale_": [120.2, 115.8, 2.1, 0.5],
      "var_": [14448.04, 13401.64, 4.41, 0.25]
    },
    "scaler_feature_names": ["chiller_1_load", "chiller_2_load", "wb_temp", "chwst_temp"],
    "scaler_hash": "sha256:e5f6g7h8..."
  },
  
  "validation_rules": {
    "allow_subset": false,
    "allow_superset": false,
    "strict_order": true,
    "case_sensitive": true
  }
}
```

### 9.3 對齊驗證流程 (Optimization 階段)

**Step 1: 完整性檢查** (E901)
```python
if not os.exists('feature_manifest.json'):
    raise E901("缺少 feature_manifest，無法驗證特徵對齊")
```

**Step 2: 特徵清單比對** (E901)
```python
expected_features = manifest['feature_specification']['feature_names']
input_features = get_input_feature_names()  # 從 Optimization 輸入取得

if expected_features != input_features:
    # 詳細差異分析
    diff = list(dictdiffer.diff(expected_features, input_features))
    raise E901(f"特徵順序不匹配: {diff}")
```

**Step 3: 雜湊驗證** (E901-optional)
```python
computed_hash = sha256(','.join(input_features).encode()).hexdigest()
if computed_hash != manifest['feature_specification']['feature_hash']:
    raise E901("特徵雜湊驗證失敗：特徵名稱或順序被修改")
```

**Step 4: 縮放參數應用** (E903)
```python
if manifest['scaling_specification']['scaler_type'] == 'StandardScaler':
    scaler = StandardScaler()
    scaler.mean_ = np.array(manifest['scaling_specification']['scaler_params']['mean_'])
    scaler.scale_ = np.array(manifest['scaling_specification']['scaler_params']['scale_'])
    
    # 驗證縮放參數長度
    if len(scaler.mean_) != len(input_features):
        raise E902(f"縮放參數長度 {len(scaler.mean_)} 與特徵數 {len(input_features)} 不匹配")
    
    # 驗證縮放參數順序（通過 feature_names 比對）
    if manifest['scaling_specification']['scaler_feature_names'] != input_features:
        raise E903("縮放參數特徵順序與輸入特徵順序不一致")
```

### 9.4 容錯與恢復策略

| 錯誤情境 | 自動恢復策略 | 人工介入 |
|:---|:---|:---|
| E901: 特徵順序錯誤 | **禁止自動恢復** | 必須檢查 ETL 流程，確認特徵產生邏輯 |
| E902: 維度不匹配 | 檢查是否缺少常數特徵（如 bias），若可補零則補零並警告 | 確認特徵工程邏輯變更 |
| E903: 縮放參數缺失 | 使用線上統計即時計算 mean/std，標記為「非確定性縮放」 | 建議重新訓練模型以固定縮放參數 |

### 9.5 與現有檢查點的整合

- **檢查點 #4** (FeatureEngineer → Model Training): 驗證 Feature Manifest 正確產生（E601, E602）
- **檢查點 #7** (Model Training → Optimization): 驗證 Feature Manifest 正確載入與比對（E901, E902, E903）

---

**簽核欄**：
- [ ] 架構師確認：檢查點定義涵蓋所有模組間介面（含 Training-Optimization）
- [ ] 技術負責人確認：錯誤代碼分層 E000-E999 無衝突，E901-E903 已正確定義
- [ ] HVAC 領域專家確認：時間基準機制與特徵對齊機制符合領域需求（精度、延遲容忍度）
- [ ] 維運負責人確認：版本相容性矩陣可指導部署決策
```

此修正版已完整納入您的三項要求：

1. **錯誤代碼分層規範**：建立 E000-E999 的完整分層架構，解決原本 E800 衝突問題（Training 與 Optimization 現在有各自獨立的 E7xx 與 E8xx 區段），並提供遷移對照表。

2. **時間基準傳遞規範**：新增第8章詳細定義 `pipeline_origin_timestamp` 機制，從 Container 初始化、跨模組傳遞、到未來資料檢查的統一基準，解決時間漂移問題。

3. **特徵對齊驗證**：新增第9章與檢查點 #7，定義 Feature Manifest 規格、雜湊驗證、縮放參數傳遞機制，並新增 E901-E903 錯誤代碼專門處理 Training-Optimization 特徵錯位風險。