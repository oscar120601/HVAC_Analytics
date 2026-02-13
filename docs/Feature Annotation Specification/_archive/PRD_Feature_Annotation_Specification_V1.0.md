# PRD v1.0: 特徵標註系統規範 (Feature Annotation Specification)

**文件版本:** v1.0 (Human-Configurable Feature Metadata)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**目標:** 建立非工程師可維護的特徵定義系統，作為 Data Team 與 Domain Expert（空調技師）之間的正式契約  
**相依模組:** Cleaner v2.2+, BatchProcessor v1.3+, Feature Engineer v1.3+  
**預估工時:** 3 ~ 4 個工程天（含 CLI 工具與驗證邏輯）

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標

1. **人機分離**: 設備工程師透過 YAML 定義特徵，無需修改 Python 程式碼
2. **多案場管理**: 支援「基礎定義 + 案場覆蓋」的繼承架構，避免重複維護
3. **防呆設計**: 透過 JSON Schema 與 Pydantic 雙重驗證，防止矛盾設定（如對目標變數生成 Lag）
4. **版本綁定**: 特徵定義版本與模型版本、ETL 版本嚴格綁定，確保可追溯性

### 1.2 設計原則

| 原則 | 說明 | 實現方式 |
|:---|:---|:---|
| **SSOT 延伸** | 特徵標註是 SSOT 的「可編輯視圖」 | `config/features/` 目錄為唯一編輯入口，程式碼僅唯讀 |
| **顯式優於隱式** | 禁止自動推斷（Auto-inference），所有欄位必須顯式定義或明確標記為 `auto_detect` | 嚴格模式下，未定義欄位觸發 `E401_UNANNOTATED_COLUMN` |
| **繼承與覆蓋** | 支援多層繼承（Base → Site → Device），避免複製貼上 | `inherit` 關鍵字與深度合併演算法 |
| **驗證左移** | 在 Cleaner 階段就驗證標註，而非等到 Feature Engineer 才發現錯誤 | `FeatureAnnotationValidator` 類別在 `ConfigLoader` 階段執行 |

---

## 2. 文件架構與繼承機制

### 2.1 目錄結構

```
config/features/                    # 特徵標註根目錄
├── schema.json                     # JSON Schema 驗證規則
├── base.yaml                       # 基礎定義（所有案場共用）
├── physical_types.yaml             # 物理類型規範（可選獨立）
└── sites/                          # 案場特定定義
    ├── cgmh_ty.yaml               # 長庚醫院桃園院區
    ├── farglory_o3.yaml           # 遠雄 O3
    └── kmuh.yaml                  # 高醫
```

### 2.2 繼承機制規範

**繼承鏈**（由底向上解析）：
```
sites/cgmh_ty.yaml 
    → base.yaml 
        → physical_types.yaml (若獨立)
            → 程式碼 SSOT (VALID_PHYSICAL_TYPES)
```

**深度合併規則**：
1. **欄位級覆蓋**: 子檔案定義的欄位完全覆蓋父檔案同名列
2. **屬性級合併**: 欄位內屬性（如 `tags`）採用「子檔案優先，但合併列表」
3. **刪除標記**: 使用 `null` 或 `~` 刪除繼承的欄位

**範例**：
```yaml
# base.yaml
columns:
  chiller_1_load:
    physical_type: "chiller_load"
    enable_lag: true

# sites/cgmh_ty.yaml
inherit: base
columns:
  chiller_1_load:
    # 完全覆蓋 base 的定義，仅保留以下
    physical_type: "chiller_load"  
    enable_lag: false              # 覆蓋為 false
    description: "一號機負載（客製）" # 新增屬性
```

---

## 3. YAML Schema 詳細規範

### 3.1 頂層結構 (Root Schema)

```yaml
schema_version: "1.0"              # 必須，用於版本相容性檢查
description: "長庚醫院特徵定義"     # 選填，文件說明
inherit: "base"                    # 選填，繼承目標（檔名不含副檔名）

# 物理類型定義（可覆蓋或擴充 SSOT）
physical_types:
  [physical_type_id]: PhysicalTypeDefinition

# 欄位標註（核心）
columns:
  [column_name]: ColumnAnnotation

# Group Policy 自動匹配規則（可選）
group_policies:
  [policy_name]: GroupPolicyRule

# 驗證規則覆蓋（可選）
validation:
  strict_mode: true                # 預設 true
  allow_unannotated: false         # 是否允許未定義欄位（自動推斷）
```

### 3.2 Physical Type 定義

```yaml
physical_types:
  temperature:
    description: "溫度感測器"
    unit: "°C"                     # 顯示單位，影響報表輸出
    si_unit: "celsius"             # 內部標準化單位（轉換用）
    valid_range: [-40.0, 100.0]    # 物理限制（Cleaner 驗證用）
    agg_method: "mean"             # 預設聚合方法（resample 用）
    default_tags: ["sensor", "hvac"] # 分類標籤
    
  chiller_load:
    description: "冰機負載"
    unit: "RT"                     # 冷凍噸
    si_unit: "kw"                  # 內部換算為 kW（1 RT = 3.517 kW）
    valid_range: [0.0, 2000.0]
    agg_method: "mean"
    enable_lag: true               # 物理類型層級預設
    enable_rolling: true
    group_policy: "chiller_assets" # 自動套用至匹配的欄位
    
  power:                           # 目標變數類型
    description: "電力"
    unit: "kW"
    is_target: true                # 標記為目標變數類型
    enable_lag: false              # 強制禁止（自動檢查）
    enable_rolling: false
```

### 3.3 Column Annotation 定義（核心）

```yaml
columns:
  # 範例 1：標準感測器
  chiller_1_temp:
    column_name: "chiller_1_temp"  # 必須，與 CSV 欄位名稱完全匹配
    physical_type: "temperature"   # 必須，引用 physical_types 或 SSOT
    description: "一號冰機出水溫度" # 建議填寫，用於文件產生
    is_target: false               # 預設 false
    enable_lag: true               # 預設繼承 physical_type，可覆蓋
    enable_rolling: true           # 預設繼承 physical_type
    lag_intervals: [1, 4, 96]      # 可選，覆蓋預設 [1, 4]
    rolling_windows: [4, 96]       # 可選，覆蓋預設
    tags: ["critical", "chiller_1"] # 可選，用於篩選與分組
    
  # 範例 2：目標變數（嚴格檢查）
  total_power_kw:
    column_name: "total_power_kw"
    physical_type: "power"
    is_target: true
    # enable_lag 與 enable_rolling 必須為 false（驗證器檢查）
    
  # 範例 3：狀態欄位（不生成統計特徵）
  chiller_1_status:
    column_name: "chiller_1_status"
    physical_type: "status"        # 離散狀態（on/off/fault）
    enable_lag: false              # 狀態通常不做 lag（或僅做 one-hot）
    enable_rolling: false
    encoding: "onehot"             # 分類編碼方式
    
  # 範例 4：時間戳（特殊處理）
  timestamp:
    column_name: "timestamp"
    physical_type: "timestamp"
    is_required: true              # 必須存在，否則報錯
    timezone: "UTC"                # 預期時區（驗證用）
```

### 3.4 Group Policy 自動匹配

```yaml
group_policies:
  chiller_assets:
    description: "所有冰機相關欄位"
    match_pattern: "^chiller_\\d+_(load|temp|flow)$"  # Regex
    physical_type: "chiller_load"  # 匹配後預設 physical_type
    rules:
      lag_intervals: [1, 4]
      rolling_windows: [4, 96, 288]
      aggregations: ["mean", "std"]
      
  cooling_tower_assets:
    match_pattern: "^ct_\\d+_.*$"
    physical_type: "temperature"
    rules:
      lag_intervals: [1, 4]
      rolling_windows: [4, 96]
```

---

## 4. 驗證規則與防呆設計 (Validation Rules)

### 4.1 語法驗證 (JSON Schema)

**檔案**: `config/features/schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["schema_version"],
  "properties": {
    "schema_version": {
      "type": "string",
      "enum": ["1.0"]
    },
    "inherit": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]+$"
    },
    "columns": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z_][a-zA-Z0-9_]*$": {
          "type": "object",
          "required": ["column_name", "physical_type"],
          "properties": {
            "is_target": { "type": "boolean" },
            "enable_lag": { "type": "boolean" },
            "enable_rolling": { "type": "boolean" }
          },
          "allOf": [
            {
              "if": {
                "properties": { "is_target": { "const": true } }
              },
              "then": {
                "properties": {
                  "enable_lag": { "const": false },
                  "enable_rolling": { "const": false }
                },
                "errorMessage": "目標變數不可啟用 Lag 或 Rolling（會導致 Data Leakage）"
              }
            }
          ]
        }
      }
    }
  }
}
```

### 4.2 語意驗證 (Pydantic Validator)

**檔案**: `src/features/annotation_validator.py`

```python
from typing import Dict, List, Set
import re
from pydantic import BaseModel, validator, root_validator

class ColumnAnnotation(BaseModel):
    column_name: str
    physical_type: str
    is_target: bool = False
    enable_lag: bool = True
    enable_rolling: bool = True
    lag_intervals: Optional[List[int]] = None
    rolling_windows: Optional[List[int]] = None
    
    @validator('physical_type')
    def validate_physical_type(cls, v):
        allowed = VALID_PHYSICAL_TYPES.keys()  # 從 SSOT 載入
        if v not in allowed and v != "timestamp":
            raise ValueError(f"未定義的 physical_type: {v}，可用的: {allowed}")
        return v
    
    @root_validator
    def validate_target_constraints(cls, values):
        """防止 Data Leakage：目標變數不可有滯後特徵"""
        is_target = values.get('is_target', False)
        enable_lag = values.get('enable_lag', True)
        enable_rolling = values.get('enable_rolling', True)
        
        if is_target:
            if enable_lag or enable_rolling:
                raise ValueError(
                    f"欄位 {values.get('column_name')} 標記為 is_target=true，"
                    f"但 enable_lag={enable_lag}, enable_rolling={enable_rolling}。"
                    f"這會導致 Data Leakage，必須設為 false。"
                )
            # 強制設定為 false（即使使用者沒寫）
            values['enable_lag'] = False
            values['enable_rolling'] = False
        return values
    
    @validator('lag_intervals')
    def validate_lag_intervals(cls, v, values):
        """驗證 lag 間隔為正整數且遞增"""
        if v is None:
            return v
        if not all(isinstance(x, int) and x > 0 for x in v):
            raise ValueError("lag_intervals 必須為正整數列表")
        if v != sorted(v):
            raise ValueError("lag_intervals 必須遞增排序")
        return v

class FeatureAnnotation(BaseModel):
    schema_version: str
    inherit: Optional[str] = None
    columns: Dict[str, ColumnAnnotation]
    
    @validator('schema_version')
    def validate_version(cls, v):
        if v != "1.0":
            raise ValueError(f"不支援的 schema_version: {v}，目前僅支援 1.0")
        return v
    
    def merge_with_parent(self, parent: 'FeatureAnnotation') -> 'FeatureAnnotation':
        """執行深度合併（子覆蓋父）"""
        merged_columns = parent.columns.copy()
        merged_columns.update(self.columns)  # 子覆蓋父
        
        return FeatureAnnotation(
            schema_version=self.schema_version,
            inherit=self.inherit,
            columns=merged_columns
        )
```

### 4.3 與實際資料一致性驗證

**時機**: Cleaner 階段（讀取 CSV 後，清洗前）

```python
def validate_against_dataframe(
    annotation: FeatureAnnotation, 
    df: pl.DataFrame
) -> None:
    """
    驗證標註與實際資料的一致性
    
    錯誤代碼:
    - E401: 有標註但資料中不存在（orphan columns）
    - E402: 有資料但無標註（unannotated columns，嚴格模式報錯）
    - E403: 型別不匹配（如標註 Float64，實際為 Utf8）
    """
    annotated_cols = set(annotation.columns.keys())
    actual_cols = set(df.columns)
    
    # 檢查必要欄位
    required = [
        name for name, col in annotation.columns.items() 
        if getattr(col, 'is_required', False)
    ]
    missing_required = set(required) - actual_cols
    if missing_required:
        raise ConfigurationError(f"E404: 缺少必要欄位: {missing_required}")
    
    # 嚴格模式：禁止未定義欄位
    unannotated = actual_cols - annotated_cols - {'timestamp'}
    if unannotated and annotation.validation.get('allow_unannotated', False) is False:
        raise ConfigurationError(
            f"E402: 資料中存在未定義的欄位: {unannotated}。"
            f"請在 feature annotation 中定義，或設定 allow_unannotated: true"
        )
    
    # 型別驗證
    for col_name, col_meta in annotation.columns.items():
        if col_name not in actual_cols:
            continue
        expected_dtype = get_expected_dtype(col_meta.physical_type)
        actual_dtype = df[col_name].dtype
        if not is_compatible(actual_dtype, expected_dtype):
            raise TypeError(
                f"E403: 欄位 {col_name} 型別不匹配: "
                f"標註預期 {expected_dtype}, 實際 {actual_dtype}"
            )
```

---

## 5. 與 ETL Pipeline 的整合點

### 5.1 整合流程圖

```
config/features/sites/cgmh_ty.yaml
        ↓
ConfigLoader.load_feature_annotation("cgmh_ty")
    - 解析繼承鏈
    - 執行深度合併
    - Pydantic 驗證
        ↓
ETLContainer (傳遞至各模組)
    ↓                   ↓                   ↓                   ↓
Cleaner v2.2      BatchProcessor v1.3  Feature Engineer v1.3  Model Training
(欄位驗證)          (寫入 Manifest)      (Group Policy)       (特徵解釋)
- E402 檢查        - feature_metadata   - 匹配 physical_type  - SHAP 解釋用
- 單位轉換         - annotation_version - 決定 Lag/Rolling    - 特徵重要性
```

### 5.2 Cleaner v2.2 整合點

**修改**: `Cleaner._build_column_metadata()` 改為讀取 Annotation

```python
def _build_column_metadata(self, df: pl.DataFrame) -> Dict[str, FeatureMetadata]:
    """從 Feature Annotation 讀取 Metadata（取代自動推斷）"""
    annotation = self.config.feature_annotation  # 由 Container 注入
    
    metadata = {}
    for col_name in df.columns:
        if col_name == "timestamp":
            continue
            
        if col_name not in annotation.columns:
            if self.config.strict_mode:
                raise ConfigurationError(f"E402: 未定義欄位 {col_name}")
            # 保守預設（僅嚴格模式關閉時）
            metadata[col_name] = FeatureMetadata(
                column_name=col_name,
                physical_type="gauge"
            )
            continue
        
        col_ann = annotation.columns[col_name]
        metadata[col_name] = FeatureMetadata(
            column_name=col_name,
            physical_type=col_ann.physical_type,
            unit=col_ann.unit,
            is_target=col_ann.is_target,
            enable_lag=col_ann.enable_lag,
            enable_rolling=col_ann.enable_rolling
        )
    
    return metadata
```

### 5.3 BatchProcessor v1.3 整合點

**修改**: Manifest 寫入 Annotation 版本資訊

```python
def _generate_manifest(self, ...):
    return Manifest(
        # ... 其他欄位
        feature_metadata=column_metadata,
        annotation_version=self.config.feature_annotation.get_version(),  # 新增
        annotation_checksum=self.config.feature_annotation.compute_checksum()  # 新增
    )
```

### 5.4 Feature Engineer v1.3 整合點

**修改**: Group Policy 使用 Annotation 定義的 physical_type

```python
def _resolve_group_policies(self, df, manifest_metadata):
    # manifest_metadata 實際來源是 Feature Annotation
    # 因此 Group Policy 完全依照人類專家的設定執行，而非自動推斷
    ...
```

---

## 6. CLI 工具規格

### 6.1 命令列表

```bash
# 驗證標註文件語法
python main.py features validate config/features/sites/cgmh_ty.yaml

# 從 CSV 自動產生標註草稿（輔助工具）
python main.py features init --from-csv data/raw/sample.csv --output config/features/sites/new_site.yaml

# 檢查標註與實際資料一致性
python main.py features check --annotation cgmh_ty --data data/raw/cgmh_ty_20250213.csv

# 比較兩版標註差異（用於版本升級）
python main.py features diff config/features/v1.0/base.yaml config/features/v1.1/base.yaml
```

### 6.2 `init` 命令詳細邏輯

```python
def init_annotation_from_csv(
    csv_path: Path, 
    output_path: Path,
    site_id: str
) -> None:
    """
    從 CSV 自動產生標註草稿（輔助工具，非自動推斷）
    
    邏輯:
    1. 讀取 CSV 欄位名稱
    2. 嘗試匹配 common patterns（如 .*temp.* → temperature）
    3. 產生 YAML 草稿，所有欄位標記為 "pending_review"
    4. 人工確認後改為正式定義
    """
    df = pl.read_csv(csv_path, n_rows=1000)
    
    template = {
        "schema_version": "1.0",
        "description": f"Auto-generated draft for {site_id}",
        "inherit": "base",
        "columns": {}
    }
    
    for col in df.columns:
        if col == "timestamp":
            template["columns"][col] = {
                "column_name": col,
                "physical_type": "timestamp",
                "is_required": True
            }
        else:
            # 簡易推斷僅用於草稿，需人工確認
            guessed_type = guess_physical_type(col)  # 基於名稱推斷
            template["columns"][col] = {
                "column_name": col,
                "physical_type": guessed_type,
                "description": "TODO: Please review and confirm",
                "tags": ["auto_generated", "pending_review"]
            }
    
    output_path.write_text(yaml.dump(template, sort_keys=False, allow_unicode=True))
    print(f"Draft annotation saved to {output_path}")
    print("WARNING: Please review all 'pending_review' tags before production use")
```

---

## 7. 版本控制與相容性

### 7.1 版本宣告與檢查

```yaml
# 文件內必須宣告
schema_version: "1.0"

# 程式碼檢查
if annotation.schema_version != SUPPORTED_VERSION:
    raise CompatibilityError(
        f"Feature Annotation version {annotation.schema_version} "
        f"not supported by this code version (supports {SUPPORTED_VERSION})"
    )
```

### 7.2 與模型版本綁定

**Model Registry 必須記錄**：
```json
{
  "model_version": "1.2.3",
  "feature_annotation_version": "cgmh_ty_v2.1",
  "feature_annotation_checksum": "sha256:abc123...",
  "column_count": 47,
  "physical_types_distribution": {
    "temperature": 12,
    "chiller_load": 3,
    "power": 1
  }
}
```

---

## 8. 錯誤代碼對照表

| 錯誤代碼 | 名稱 | 階段 | 說明 |
|:---|:---|:---:|:---|
| **E400** | `SCHEMA_VALIDATION_FAILED` | 載入時 | YAML 語法不符合 schema.json |
| **E401** | `ORPHAN_COLUMN` | 驗證時 | 標註檔案中有欄位在實際資料中不存在（Warning） |
| **E402** | `UNANNOTATED_COLUMN` | Cleaner | 實際資料中有欄位未定義（嚴格模式報錯） |
| **E403** | `TYPE_MISMATCH` | Cleaner | 欄位型別與 physical_type 預期不符 |
| **E404** | `REQUIRED_COLUMN_MISSING` | Cleaner | 標記 is_required 的欄位不存在 |
| **E405** | `TARGET_LEAKAGE_RISK` | 驗證時 | is_target=true 但 enable_lag/rolling 未設為 false |
| **E406** | `INHERITANCE_ERROR` | 載入時 | 繼承的父檔案不存在或循環繼承 |
| **E407** | `VERSION_MISMATCH` | 載入時 | schema_version 不被支援 |

---

## 9. 交付物清單

### 9.1 配置文件
1. `config/features/schema.json` - JSON Schema 驗證規則
2. `config/features/base.yaml` - 基礎特徵定義範本
3. `config/features/physical_types.yaml` - 物理類型規範（可選獨立）
4. `config/features/sites/cgmh_ty.yaml` - 長庚醫院範例
5. `config/features/sites/farglory_o3.yaml` - 遠雄範例

### 9.2 程式碼檔案
6. `src/features/annotation_models.py` - Pydantic 模型（ColumnAnnotation, FeatureAnnotation）
7. `src/features/annotation_loader.py` - 載入器（含繼承解析）
8. `src/features/annotation_validator.py` - 驗證器（語意檢查）
9. `src/utils/config_loader.py` - 擴充 `load_feature_annotation()` 方法

### 9.3 CLI 工具
10. `src/cli/features_cli.py` - `main.py features` 子命令實作

### 9.4 文件
11. `docs/features/FEATURE_ANNOTATION_v1.0.md` - 本文件
12. `docs/features/TROUBLESHOOTING.md` - 常見錯誤排解

---

## 10. 驗收簽核 (Sign-off Checklist)

- [ ] **YAML Schema**: `schema.json` 正確驗證欄位型別與結構
- [ ] **繼承機制**: `sites/cgmh_ty.yaml` 正確繼承並覆蓋 `base.yaml`
- [ ] **防呆驗證**: `is_target=true` 且 `enable_lag=true` 時正確拋出 E405
- [ ] **Cleaner 整合**: 未定義欄位在嚴格模式下正確拋出 E402
- [ ] **Manifest 傳遞**: BatchProcessor 正確寫入 annotation_version 與 checksum
- [ ] **Group Policy**: Feature Engineer 依照 annotation 的 physical_type 正確匹配
- [ ] **CLI 工具**: `features validate`, `init`, `check`, `diff` 命令可用
- [ ] **版本綁定**: Model Registry 正確記錄 feature_annotation_checksum

---