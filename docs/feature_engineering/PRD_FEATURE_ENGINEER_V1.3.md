# PRD v1.3: 特徵工程強健性實作指南 (Feature Engineering Implementation Guide)
# 整合 Feature Annotation v1.2：Metadata 消費與 Group Policy 重構

**文件版本:** v1.3-FA (Feature Annotation Consumption & Device Role Awareness)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**目標模組:** `src/etl/feature_engineer.py` (v1.3+)  
**上游契約:** `src/etl/batch_processor.py` (v1.3-FA+, 檢查點 #3)  
**下游契約:** `src/modeling/training_pipeline.py` (v1.0+, 輸出檢查點)  
**關鍵相依:** `src/features/annotation_manager.py` (v1.2+, 提供 device_role 與 ignore_warnings 查詢)  
**預估工時:** 5 ~ 6 個工程天（含 Annotation 整合與 Group Policy 重構）

---

## 1. 執行總綱與設計哲學

### 1.1 版本變更總覽 (v1.2 → v1.3-FA)

| 變更類別 | v1.2 狀態 | v1.3-FA 修正 | 影響層級 |
|:---|:---|:---|:---:|
| **Metadata 來源** | 依賴 `get_feature_meta()` (重新探測) | **從 Manifest 接收** `feature_metadata` (物理屬性) + **直接查詢** Annotation (device_role) | 🔴 Critical |
| **device_role 消費** | 無 | **直接讀取** FeatureAnnotationManager (Cleaner 不傳遞，職責分離) | 🔴 Critical |
| **Group Policy 更新** | 使用推斷的 physical_type | **使用 Annotation SSOT** 的 physical_type 與 device_role | 🔴 Critical |
| **ignore_warnings** | 無 | **查詢 Annotation** 決定是否抑制特定警告 (W403) | 🟡 Medium |
| **Flags 硬編碼** | Step 3.2 硬編碼 flags | **強制引用** `VALID_QUALITY_FLAGS` (SSOT) | 🔴 Critical |
| **稽核軌跡** | 無版本記錄 | **驗證** `annotation_audit_trail` (schema_version, inheritance_chain) | 🟡 Medium |
| **Data Leakage** | `shift(1)` 防護 | **保留** `shift(1)` + `cutoff_timestamp` 嚴格檢查 | 🔴 Critical |

### 1.2 核心設計原則

1. **SSOT 嚴格遵守**: 所有 quality flags 操作引用 `VALID_QUALITY_FLAGS`；所有 physical_type 與 device_role 決策引用 FeatureAnnotationManager
2. **Metadata 分層消費**:
   - **物理屬性** (physical_type, unit)：從 BatchProcessor Manifest 的 `feature_metadata` 讀取
   - **設備角色** (device_role, ignore_warnings)：直接查詢 FeatureAnnotationManager (YAML SSOT)
3. **職責分離尊重**: 不期待 Cleaner/BatchProcessor 傳遞 device_role，主動從 Annotation 層查詢
4. **Group Policy 語意感知**: 根據 device_role (primary/backup/seasonal) 調整統計特徵生成策略（如備用設備使用不同窗口）
5. **繼承鏈相容**: 正確處理 `inheritance_chain`，支援 base → site 的設定覆蓋

---

## 2. 介面契約規範 (Interface Contracts)

### 2.1 輸入契約 (Input Contract from BatchProcessor v1.3-FA)

**檢查點 #3: BatchProcessor → Feature Engineer**

```python
# 標準讀取範例 (必須實作)
def load_from_batch_processor(manifest_path: Path) -> Tuple[pl.LazyFrame, Dict, Dict]:
    """
    Returns:
        df: LazyFrame (Parquet 資料，INT64/UTC 驗證通過，不含 device_role)
        feature_metadata: Dict (column_name -> physical_type/unit，不含 device_role)
        annotation_audit_trail: Dict (schema_version, inheritance_chain, yaml_checksum)
    """
    manifest = Manifest.parse_file(manifest_path)
    
    # 1. 驗證 Manifest 完整性 (E301)
    if not manifest.validate_checksum():
        raise ContractViolationError("E301: Manifest 損毀")
    
    # 2. 【新增】驗證 Annotation 稽核軌跡 (E400)
    audit = manifest.annotation_audit_trail
    if audit:
        expected_ver = FEATURE_ANNOTATION_CONSTANTS['expected_schema_version']
        if audit.get('schema_version') != expected_ver:
            raise ConfigurationError(
                f"E400: Manifest 的 Annotation 版本過舊 "
                f"({audit.get('schema_version')} vs {expected_ver})"
            )
    
    # 3. 讀取資料與 Metadata
    files = [manifest_path.parent / f for f in manifest.output_files]
    df = pl.scan_parquet(files)
    
    return (
        df, 
        manifest.feature_metadata,  # 僅含物理屬性
        audit  # 稽核資訊
    )
```

| 檢查項 | 規範 | 錯誤代碼 | 處理 |
|:---|:---|:---:|:---|
| Manifest 完整性 | `checksum` 驗證通過 | E301 | 拒絕讀取 |
| Annotation 版本 | `schema_version` 符合 SSOT | E400 | 終止流程 |
| timestamp 格式 | `INT64`, `nanoseconds`, `UTC` | E302 | 拒絕讀取 |
| quality_flags 值 | ⊆ `VALID_QUALITY_FLAGS` | E303 | 拒絕讀取 |
| **device_role 欄位** | **禁止存在於 DataFrame** | E500 | 終止流程 |
| feature_metadata | 非空 (建議) | E304 (Warning) | 使用保守預設 |

### 2.2 Annotation 直接查詢契約

**Feature Engineer 直接實例化 FeatureAnnotationManager**:

```python
# 在 FeatureEngineer.__init__ 或 transform 中
self.annotation_manager = FeatureAnnotationManager(
    site_id=site_id,
    yaml_base_dir=config.feature_annotation.yaml_base_dir
)

# 查詢 device_role (因 Cleaner 未傳遞)
device_role = self.annotation_manager.get_column_config(col).device_role

# 查詢是否抑制警告
should_ignore = self.annotation_manager.should_ignore_warning(col, "W403")
```

### 2.3 輸出契約 (Output Contract to Model Training)

**填補 GAP #5: Feature Engineer → Model Training**

```python
class FeatureEngineerOutputContract:
    """Feature Engineer v1.3-FA 輸出規範"""
    
    # 1. 特徵矩陣 (Parquet 格式)
    feature_matrix: pl.DataFrame
    
    # 2. 目標變數資訊
    target_variable: Optional[str]
    target_metadata: Optional[FeatureMetadata]
    
    # 3. Quality Flag 特徵 (SSOT 同步)
    quality_flag_features: List[str]
    
    # 4. 【新增】Annotation 稽核資訊 (供 Training Pipeline 記錄)
    annotation_context: Dict = {
        "schema_version": "1.2",
        "inheritance_chain": "base -> cgmh_ty",
        "yaml_checksum": "sha256:...",
        "group_policies_applied": ["chillers", "towers"]
    }
    
    # 5. 防 Data Leakage 資訊
    train_test_split_info: Dict = {
        "temporal_cutoff": datetime,
        "strict_past_only": True,
        "excluded_future_rows": int
    }
    
    # 6. 特徵元資料 (供 Model 解釋性使用)
    feature_metadata: Dict[str, FeatureMetadata]
    
    # 7. 版本追蹤
    feature_engineer_version: str = "1.3-FA"
    upstream_manifest_id: str
```

---

## 3. 分階段實作計畫 (Phase-Based Implementation)

### Phase 0: Annotation Manager 整合基礎建設 (Day 1, 新增)

#### Step 0.1: SSOT 嚴格引用與 Manager 注入

**檔案**: `src/etl/feature_engineer.py` (頂部)

**實作內容**:
```python
from typing import Dict, List, Optional, Union, Final, Tuple
from datetime import datetime
from pathlib import Path
import polars as pl
import numpy as np
from pydantic import BaseModel

# 【關鍵】SSOT 嚴格引用
from src.etl.config_models import (
    VALID_QUALITY_FLAGS,      # SSOT: 6個標準品質標記
    TIMESTAMP_CONFIG,         # SSOT: UTC, ns
    FeatureMetadata,          # SSOT: 欄位元資料 (物理屬性)
    FeatureEngineeringConfig,
    FEATURE_ANNOTATION_CONSTANTS
)

# 【新增】直接查詢 Annotation SSOT
from src.features.annotation_manager import FeatureAnnotationManager, ColumnAnnotation

# 錯誤代碼 (Interface Contract v1.0)
ERROR_CODES: Final[Dict[str, str]] = {
    "E301": "MANIFEST_INTEGRITY_FAILED",
    "E302": "SCHEMA_MISMATCH",
    "E303": "UNKNOWN_QUALITY_FLAG",
    "E304": "METADATA_MISSING",
    "E305": "DATA_LEAKAGE_DETECTED",
    "E400": "ANNOTATION_VERSION_MISMATCH",  # 【新增】
    "E402": "ANNOTATION_NOT_FOUND",         # 【新增】
    "E500": "DEVICE_ROLE_LEAKAGE"           # 【新增】
}
```

#### Step 0.2: 建構子與 AnnotationManager 初始化

**檔案**: `src/etl/feature_engineer.py` (`FeatureEngineer.__init__`)

```python
class FeatureEngineer:
    """
    Feature Engineer v1.3-FA - 整合 Feature Annotation 消費
    
    核心職責：
    1. 從 Manifest 讀取物理屬性 (physical_type, unit)
    2. 【新增】直接查詢 Annotation SSOT 取得 device_role 與 ignore_warnings
    3. 應用語意感知的 Group Policy (根據 device_role 調整策略)
    4. 確保不產生 Data Leakage
    """
    
    def __init__(
        self, 
        config: FeatureEngineeringConfig,
        site_id: str,
        yaml_base_dir: str = "config/features/sites"  # 【新增】Annotation 路徑
    ):
        self.config = config
        self.site_id = site_id
        self.logger = get_logger("FeatureEngineer")
        
        # 【關鍵】直接初始化 AnnotationManager (職責分離：不依赖 Cleaner 傳遞)
        self.annotation_manager = FeatureAnnotationManager(
            site_id=site_id,
            yaml_base_dir=yaml_base_dir
        )
        
        self.logger.info(
            f"初始化 FeatureEngineer (Schema: {self.annotation_manager.schema_version}, "
            f"繼承鏈: {self.annotation_manager.inheritance_chain})"
        )
    
    def validate_annotation_compatibility(self, audit_trail: Dict):
        """
        驗證 Annotation 版本相容性 (E400)
        """
        if not audit_trail:
            self.logger.warning("Manifest 缺少 annotation_audit_trail")
            return
        
        schema_ver = audit_trail.get('schema_version')
        expected = FEATURE_ANNOTATION_CONSTANTS['expected_schema_version']
        
        if schema_ver != expected:
            raise ConfigurationError(
                f"E400: Annotation Schema 版本不符。期望: {expected}, 實際: {schema_ver}"
            )
        
        # 驗證繼承鏈一致性 (可選，用於除錯)
        manifest_chain = audit_trail.get('inheritance_chain', '')
        manager_chain = self.annotation_manager.inheritance_chain
        if manifest_chain != manager_chain:
            self.logger.warning(
                f"繼承鏈不一致: Manifest={manifest_chain}, Manager={manager_chain}"
            )
```

---

### Phase 1: 輸入驗證與 Manifest 讀取 (Day 1-2)

#### Step 1.1: 讀取與驗證（更新版）

**方法**: `load_from_manifest(manifest_path: Path) -> Tuple[...]`

**詳細邏輯**:
```python
def load_from_manifest(
    self, 
    manifest_path: Path
) -> Tuple[pl.LazyFrame, Dict[str, FeatureMetadata], Dict]:
    """
    從 BatchProcessor v1.3-FA Manifest 讀取資料與 Metadata
    
    【關鍵】回傳 annotation_audit_trail 供後續驗證
    """
    from src.etl.manifest import Manifest
    
    manifest = Manifest.parse_file(manifest_path)
    
    # 1. 驗證 Manifest 完整性 (E301)
    if not manifest.validate_checksum():
        raise ContractViolationError(f"E301: Manifest 完整性驗證失敗: {manifest_path}")
    
    # 2. 驗證 Annotation 稽核軌跡 (E400)
    audit_trail = getattr(manifest, 'annotation_audit_trail', {})
    if audit_trail:
        self.validate_annotation_compatibility(audit_trail)
    else:
        self.logger.warning("Manifest 缺少 annotation_audit_trail，跳過版本檢查")
    
    # 3. 驗證 SSOT 版本相容性 (quality_flags)
    if set(manifest.quality_flags_schema) != set(VALID_QUALITY_FLAGS):
        self.logger.warning(
            f"Manifest flags 版本與 SSOT 不同: "
            f"Manifest={manifest.quality_flags_schema}, SSOT={VALID_QUALITY_FLAGS}"
        )
    
    # 4. 驗證 timestamp Schema (E302)
    ts_schema = manifest.timestamp_schema
    if ts_schema.get("format") != "INT64" or ts_schema.get("timezone") != "UTC":
        raise ContractViolationError(f"E302: Timestamp schema 不符: {ts_schema}")
    
    # 5. 讀取 Parquet
    files = [manifest_path.parent / f for f in manifest.output_files]
    if not files:
        raise DataValidationError(f"Manifest 未包含輸出檔案: {manifest_path}")
    
    df = pl.scan_parquet(files)
    
    # 6. 【關鍵】驗證 DataFrame 不含 device_role (E500)
    if "device_role" in df.columns:
        raise ContractViolationError(
            f"E500: DataFrame 包含禁止欄位 'device_role'。 "
            f"Cleaner 不應傳遞 device_role，Feature Engineer 應直接查詢 Annotation。"
        )
    
    # 7. 檢查 feature_metadata (E304)
    metadata = manifest.feature_metadata
    if not metadata:
        if self.config.input_contract.enforce_manifest_metadata:
            raise ContractViolationError("E304: Manifest 缺少 feature_metadata")
        else:
            self.logger.warning("E304: 使用保守預設")
            metadata = self._infer_metadata_conservative(df)
    
    return df, metadata, audit_trail
```

---

### Phase 2: SSOT 合規的 Flags 處理 (Day 2)

#### Step 2.1: Quality Flags 處理（SSOT 引用）

**方法**: `_handle_quality_flags(df: pl.DataFrame) -> pl.DataFrame`

**詳細邏輯**:
```python
def _handle_quality_flags(self, df: pl.DataFrame) -> pl.DataFrame:
    """
    處理 Quality Flags (SSOT 合規版本)
    
    【關鍵】引用 VALID_QUALITY_FLAGS，無硬編碼
    """
    strategy = self.config.input_contract.quality_flags_handling
    
    if strategy == "drop":
        has_flags = pl.col("quality_flags").list.len() > 0
        return df.filter(~has_flags)
    
    elif strategy == "onehot":
        # 【SSOT 引用】動態獲取所有合法 flags
        all_flags = VALID_QUALITY_FLAGS  # ✅ 正確: 引用 SSOT
        
        generated_flags = []
        for flag in all_flags:
            col_name = f"is_{flag.lower()}_flag"
            df = df.with_columns(
                pl.col("quality_flags")
                .list.contains(flag)
                .alias(col_name)
            )
            generated_flags.append(col_name)
        
        self.quality_flag_features = generated_flags
        return df
    
    return df
```

---

### Phase 3: 語意感知 Group Policy (Day 3-4, 核心更新)

#### Step 3.1: Group Policy 解析（使用 Annotation SSOT）

**方法**: `_resolve_group_policies(metadata: Dict) -> Dict[str, StatsRule]`

**詳細邏輯**:
```python
def _resolve_group_policies(
    self, 
    manifest_metadata: Dict[str, FeatureMetadata]
) -> Dict[str, StatsRule]:
    """
    解析 Group Policies，使用 Annotation SSOT (physical_type + device_role)
    
    【關鍵修正】v1.2 僅使用 physical_type；v1.3-FA 增加 device_role 感知
    """
    resolved = {}
    
    for policy in self.config.stats_features.group_policies:
        target_cols = []
        
        for col, meta in manifest_metadata.items():
            # 1. 匹配 physical_type (來自 Manifest)
            if meta.physical_type not in policy.apply_to_types:
                continue
            
            # 2. 【新增】查詢 device_role (來自 AnnotationManager)
            col_config = self.annotation_manager.get_column_config(col)
            if not col_config:
                self.logger.warning(f"欄位 {col} 在 Annotation 中未定義，跳過 Group Policy")
                continue
            
            device_role = col_config.device_role
            
            # 3. 【新增】根據 device_role 調整策略
            if device_role == "backup" and policy.name == "High_Freq":
                # 備用設備不使用高頻採樣策略（可能長期停機）
                self.logger.debug(f"欄位 {col} (backup) 跳過 High_Freq 策略")
                continue
            
            if device_role == "seasonal" and policy.name == "Strict_Balance":
                # 季節性設備放寬平衡檢查
                self.logger.debug(f"欄位 {col} (seasonal) 放寬 Strict_Balance")
            
            # 4. 排除目標變數 (Data Leakage 防護)
            if meta.is_target:
                continue
            
            target_cols.append(col)
        
        # 5. 應用規則 (含繼承處理)
        for col in target_cols:
            if (self.config.stats_features.column_overrides and 
                col in self.config.stats_features.column_overrides):
                resolved[col] = self.config.stats_features.column_overrides[col]
            else:
                # 【新增】根據 device_role 調整窗口大小
                col_config = self.annotation_manager.get_column_config(col)
                base_rule = policy.rules
                
                if col_config and col_config.device_role == "backup":
                    # 備用設備使用較大窗口（平滑長期停機影響）
                    adjusted_rule = self._adjust_rule_for_backup(base_rule)
                    resolved[col] = adjusted_rule
                else:
                    resolved[col] = base_rule
    
    return resolved

def _adjust_rule_for_backup(self, base_rule: StatsRule) -> StatsRule:
    """
    為備用設備調整統計規則 (設備角色感知)
    """
    # 備用設備：增大 rolling window，減少 lag 數量
    adjusted = base_rule.copy()
    
    if adjusted.rolling_windows:
        # 窗口增大 2 倍（但不超过 96）
        adjusted.rolling_windows = [
            min(w * 2, 96) for w in adjusted.rolling_windows
        ]
    
    if adjusted.lag_intervals:
        # 只保留前 2 個 lag
        adjusted.lag_intervals = adjusted.lag_intervals[:2]
    
    return adjusted
```

#### Step 3.2: 統計特徵生成（Data Leakage 防護 + 警告抑制）

**方法**: `_generate_stats_features(df: pl.DataFrame, column_rules: Dict) -> pl.DataFrame`

**詳細邏輯**:
```python
def _generate_stats_features(
    self, 
    df: pl.DataFrame, 
    column_rules: Dict[str, StatsRule]
) -> pl.DataFrame:
    """
    生成統計特徵，支援 device_role 感知與 ignore_warnings
    """
    expressions = []
    
    for col, rules in column_rules.items():
        if col not in df.columns:
            continue
        
        # 【新增】查詢 ignore_warnings (來自 Annotation)
        col_config = self.annotation_manager.get_column_config(col)
        ignore_warnings = col_config.ignore_warnings if col_config else []
        
        # Lag 特徵 (Data Leakage 防護：shift)
        for lag in rules.lag_intervals:
            if lag > len(df) * 0.5:
                # 【新增】檢查是否應忽略 W402 (窗口過大警告)
                if "W402" not in ignore_warnings:
                    self.logger.warning(f"W402: 欄位 {col} lag {lag} 超過資料長度 50%")
                continue
            
            expressions.append(
                pl.col(col).shift(lag).alias(f"{col}_lag_{lag}")
            )
        
        # Rolling 特徵 (嚴格 shift(1) 防護)
        for window in rules.rolling_windows:
            if window > len(df) * 0.5:
                if "W402" not in ignore_warnings:
                    self.logger.warning(f"W402: 欄位 {col} window {window} 超過 50%")
                continue
            
            # 這裡省略具體 rolling 計算，與原邏輯相同
            # ...
    
    return df.with_columns(expressions) if expressions else df
```

---

### Phase 4: 輸出準備與 Model Training 銜接 (Day 4-5)

#### Step 4.1: 輸出契約建構（更新版）

**方法**: `_build_output_contract(...) -> FeatureEngineerOutputContract`

```python
def _build_output_contract(
    self, 
    df: pl.DataFrame, 
    manifest: Manifest,
    audit_trail: Dict,
    target_col: Optional[str] = None
) -> FeatureEngineerOutputContract:
    """
    建構輸出契約，包含 Annotation 上下文
    """
    # 目標變數處理
    target_metadata = None
    if target_col and target_col in manifest.feature_metadata:
        target_metadata = manifest.feature_metadata[target_col]
    
    # 特徵元資料 (標記 derived)
    feature_metadata = {}
    for col in df.columns:
        if col in ["timestamp", target_col]:
            continue
        
        if col in manifest.feature_metadata:
            feature_metadata[col] = manifest.feature_metadata[col]
        else:
            feature_metadata[col] = FeatureMetadata(
                column_name=col,
                physical_type="derived",
                is_target=False
            )
    
    # 【新增】Annotation 上下文 (供 Training Pipeline 記錄)
    annotation_context = {
        "schema_version": audit_trail.get('schema_version', 'unknown'),
        "inheritance_chain": audit_trail.get('inheritance_chain', 'none'),
        "yaml_checksum": audit_trail.get('yaml_checksum', ''),
        "group_policies_applied": [
            p.name for p in self.config.stats_features.group_policies
        ],
        "device_role_aware": True  # 標記已應用設備角色感知
    }
    
    return FeatureEngineerOutputContract(
        feature_matrix=df,
        target_variable=target_col,
        target_metadata=target_metadata,
        quality_flag_features=getattr(self, 'quality_flag_features', []),
        annotation_context=annotation_context,  # 【新增】
        train_test_split_info={
            "temporal_cutoff": self.config.cutoff_timestamp.isoformat() if self.config.cutoff_timestamp else None,
            "strict_past_only": True
        },
        feature_metadata=feature_metadata,
        upstream_manifest_id=manifest.batch_id,
        feature_engineer_version="1.3-FA"
    )
```

---

## 4. 錯誤代碼對照表 (Error Codes)

| 錯誤代碼 | 名稱 | 發生階段 | 說明 | 處理建議 |
|:---|:---|:---:|:---|:---|
| **E301** | `MANIFEST_INTEGRITY_FAILED` | Step 1.1 | Manifest checksum 驗證失敗 | 重新執行 BatchProcessor |
| **E302** | `SCHEMA_MISMATCH` | Step 1.1 | Parquet Schema 非 INT64/UTC | 重新執行 BatchProcessor |
| **E303** | `UNKNOWN_QUALITY_FLAG` | Step 2.1 | 輸入含未定義 flags | 確認 SSOT 版本一致性 |
| **E304** | `METADATA_MISSING` | Step 1.1 | Manifest 無 feature_metadata | 升級 BatchProcessor |
| **E305** | `DATA_LEAKAGE_DETECTED` | Step 3.2 | 包含未來資料 | 檢查 cutoff_timestamp |
| **E400** | `ANNOTATION_VERSION_MISMATCH` | Step 0.2/1.1 | Manifest 的 Annotation 版本過舊 | 執行 migrate-excel |
| **E402** | `ANNOTATION_NOT_FOUND` | Step 3.1 | 欄位未定義於 Annotation | 執行 features wizard |
| **E500** | `DEVICE_ROLE_LEAKAGE` | Step 1.1 | DataFrame 含 device_role 欄位 | 檢查 Cleaner 職責分離 |

---

## 5. 測試與驗證計畫 (Test Plan)

### 5.1 單元測試 (Unit Tests)

| 測試案例 ID | 描述 | 輸入 | 預期結果 | 對應 Step |
|:---|:---|:---|:---|:---:|
| **FE13-FA-01** | E400 版本檢查 | Manifest schema_version=1.1 | 拋出 E400 | 0.2 |
| **FE13-FA-02** | device_role 查詢 | 呼叫 annotation_manager | 正確取得 primary/backup/seasonal | 3.1 |
| **FE13-FA-03** | Group Policy 設備感知 | backup 設備套用 High_Freq | 策略被跳過 | 3.1 |
| **FE13-FA-04** | ignore_warnings 生效 | 標記 W403 忽略 | 不觸發高零值警告 | 3.2 |
| **FE13-FA-05** | 繼承鏈驗證 | cgmh_ty 繼承 base | 正確解析繼承的 physical_types | 3.1 |
| FE13-001 | SSOT Flags 引用 | VALID_QUALITY_FLAGS 更新 | One-hot 自動包含新 flag | 2.1 |
| FE13-002 | Metadata 接收 | Manifest 含 physical_type | Group Policy 正確套用 | 3.1 |

### 5.2 整合測試 (Integration Tests)

| 測試案例 ID | 描述 | 上游 | 下游 | 驗證目標 |
|:---|:---|:---:|:---:|:---|
| **INT-FE-FA-01** | 完整 Metadata 消費 | BP v1.3-FA (audit_trail) + Annotation YAML | FE v1.3-FA | 正確讀取 device_role，應用語意策略 |
| **INT-FE-FA-02** | Backup 設備特徵 | Backup 設備資料 | FE v1.3-FA | 使用放大窗口，不觸發 W403 |
| **INT-FE-FA-03** | 繼承鏈一致性 | base.yaml + site.yaml | FE v1.3-FA | 正確合併 Group Policies |
| INT-F01 | BP v1.3 → FE v1.3 | BP v1.3 | FE v1.3-FA | 正確接收 metadata |
| INT-F02 | FE → Model Training | FE v1.3-FA | Training Pipeline | 傳遞 annotation_context |

---

## 6. 風險評估與緩解 (Risk Assessment)

| 風險 | 嚴重度 | 可能性 | 緩解措施 |
|:---|:---:|:---:|:---|
| **Annotation 版本漂移** (E400) | 🔴 High | Medium | 啟動時嚴格檢查 schema_version |
| **device_role 查詢失敗** | 🔴 High | Low | 欄位未定義時拋出 E402，不允許預設值 |
| **SSOT 不同步** (flags) | 🔴 High | Medium | 比對 manifest.quality_flags_schema 與 VALID_QUALITY_FLAGS |
| **Data Leakage** (shift 錯誤) | 🔴 Critical | Low | 單元測試驗證 T 時刻特徵不包含 T 時刻值 |
| **繼承鏈複雜度** | 🟡 Medium | Medium | 記錄 inheritance_chain 供除錯，驗證合併結果 |

---

## 7. 版本相容性矩陣 (Version Compatibility)

| BatchProcessor | Feature Engineer | Feature Annotation | 相容性 | 說明 |
|:---:|:---:|:---:|:---:|:---|
| v1.3-FA (audit_trail) | **v1.3-FA** | v1.2 | ✅ **完全相容** | 推薦配置，支援 device_role 感知 |
| v1.3-FA | **v1.3-FA** | v1.1 | ⚠️ **降級相容** | 缺少 device_role，使用預設 primary |
| v1.3 | **v1.3-FA** | v1.2 | ⚠️ **部分相容** | 缺少 audit_trail，跳過版本檢查 |
| v1.2 | **v1.3-FA** | 任意 | ❌ **不相容** | 無法讀取 feature_metadata，拋出 E304 |

---

## 8. 交付物清單 (Deliverables)

### 8.1 程式碼檔案
1. `src/etl/feature_engineer.py` - 主要實作 (v1.3-FA，含 AnnotationManager 整合)
2. `src/etl/config_models.py` - 更新 FeatureEngineeringConfig (支援 device_role 感知)
3. `src/etl/manifest.py` - 更新 Manifest 模型 (接收 annotation_audit_trail)

### 8.2 測試檔案
4. `tests/test_feature_engineer_v13_fa.py` - v1.3-FA 專屬測試 (device_role 感知)
5. `tests/test_group_policy_device_role.py` - Group Policy 設備角色測試
6. `tests/test_annotation_integration_fe.py` - 與 AnnotationManager 整合測試

### 8.3 文件檔案
7. `docs/feature_engineering/PRD_FEATURE_ENGINEER_v1.3-FA.md` - 本文件
8. `docs/feature_engineering/DEVICE_ROLE_GUIDE.md` - device_role 與 Group Policy 使用說明

---

## 9. 驗收簽核 (Sign-off Checklist)

- [ ] **SSOT 引用**: 無硬編碼 flags，全部引用 `VALID_QUALITY_FLAGS`
- [ ] **Metadata 分層消費**: 
  - [ ] physical_type/unit 從 Manifest 讀取
  - [ ] device_role/ignore_warnings 從 AnnotationManager 查詢
- [ ] **職責分離尊重**: 不期待輸入 DataFrame 包含 device_role，直接查詢 YAML SSOT
- [ ] **Group Policy 語意感知**: 
  - [ ] backup 設備正確跳過 High_Freq 策略
  - [ ] seasonal 設備正確放寬 Strict_Balance
- [ ] **警告抑制**: 標記 ignore_warnings 的欄位正確抑制 W402/W403
- [ ] **版本檢查**: Manifest 的 schema_version 不符時正確拋出 E400
- [ ] **繼承鏈處理**: 正確消費繼承自 base.yaml 的 Group Policies
- [ ] **Data Leakage**: `shift(1)` 正確實作，驗證通過
- [ ] **輸出契約**: 正確產生 `annotation_context` 供 Training Pipeline 記錄
- [ ] **下游銜接**: Model Training 可正確讀取輸出，包含設備角色資訊

---

**關鍵設計確認**：
1. Feature Engineer **主動查詢** device_role (因 Cleaner 不傳遞)
2. Group Policy 同時使用 **physical_type** (Manifest) 與 **device_role** (Annotation)
3. **ignore_warnings** 直接查詢 Annotation，不經由 Manifest 傳遞
4. **繼承鏈** 透過 AnnotationManager 處理，與 Manifest 的 audit_trail 交叉驗證