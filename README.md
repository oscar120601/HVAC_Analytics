# HVAC Analytics - Core Engine (v1.3 Architecture)

**核心引擎狀態**: ✅ **Sprint 2 已完成 (3/3 完成，Parser A級 / Cleaner A級 / BP 通過)**  
**審查報告**: [Sprint 2 Review Report](docs/專案任務排程/Sprint_2_Review_Report.md) - Parser v2.1 (A級), Cleaner v2.2 (A級), BatchProcessor v1.3 (A-級)  
**最後更新**: 2026-02-24

---

## 📊 專案進度總覽

| Sprint | 任務 | 狀態 | 測試/展示 |
|:---:|:---|:---:|:---:|
| 1 | 1.1 Interface Contract v1.1 | ✅ 已完成 | 已驗證 |
| 1 | 1.2 System Integration v1.2 | ✅ 已完成 | 35/35 通過 |
| 1 | 1.3 Feature Annotation v1.3 | ✅ 已完成 | 18/18 通過 |
| 1 | 1.4 程式碼審查優化 | ✅ 已完成 | 72/72 通過 |
| 1 | **1.5 Sprint 1 Demo 展示** | ✅ **已完成** | **[🎨 查看 Demo](tools/demo/index.html)** |
| 2 | 2.1 Parser v2.1 | ✅ **已完成** | 16/16 通過 🟢 A級 |
| 2 | 2.2 Cleaner v2.2 | ✅ **已完成** | 26/26 通過 🟢 A級 |
| 2 | 2.3 BatchProcessor v1.3 | ✅ **已完成** | 32/32 通過 🟡 A-級 |

**Sprint 1 總計**: 53 項測試全部通過 ✅  
**Sprint 2 總計**: 74 項測試全部通過 ✅  
**累計測試**: 127 項全部通過 ✅  
**Sprint 2 狀態**: 3/3 完成 (Parser v2.1 🟢 A級, Cleaner v2.2 🟢 A級, BatchProcessor v1.3 🟡 A-級)

[📋 查看完整任務排程](./docs/專案任務排程/專案任務排程文件.md) | [📈 Sprint 1 執行摘要](./docs/專案任務排程/Sprint_1_執行摘要.md) | [📋 Sprint 1 審查報告](./docs/專案任務排程/Sprint_1_Review_Report.md) | [📈 Sprint 2 執行摘要](./docs/專案任務排程/Sprint_2_執行摘要.md) | [📋 Sprint 2 審查報告](./docs/專案任務排程/Sprint_2_Review_Report.md)

---

## 🔍 專案概覽

HVAC 冰水系統資料處理與分析的核心引擎，專注於提供高可信度 (High-Fidelity) 的 ETL 管道與物理感知 (Physics-Aware) 的能耗優化模型。本專案核心目標是建立後端工程師可輕鬆整合的黑盒子模組，並確保設備邏輯一致性與時間基準準確性。

### 設計原則

- **契約導向設計 (Contract-First)**: 嚴格定義模組間介面與檢查點
- **單一真相源 (SSOT)**: 所有配置與常數集中管理
- **Foundation First**: 基礎設施優先，確保下游模組有穩固依賴
- **Fail Fast**: 寧可終止流程，也不傳遞可疑資料

---

## 📁 專案結構 (v1.3)

```
HVAC_Analytics/
├── src/                        # 核心源碼
│   ├── container.py            # ✅ ETLContainer (4步驟初始化)
│   ├── context.py              # ✅ PipelineContext (時間基準)
│   ├── features/               # ✅ Feature Annotation v1.3
│   │   ├── __init__.py
│   │   ├── models.py           # ✅ Pydantic 模型
│   │   └── annotation_manager.py  # ✅ FeatureAnnotationManager
│   ├── interface.py            # ★ Facade - 後端整合入口
│   ├── schemas.py              # Pydantic I/O 定義
│   ├── etl/                    # ETL 管道
│   │   ├── parser.py           # ✅ v2.1 報表解析 (E1xx Error Codes)
│   │   ├── cleaner.py          # ✅ v2.2 資料清洗 + Equipment Precheck (E2xx/E3xx/E5xx)
│   │   ├── batch_processor.py  # v1.3 批次處理 + Manifest (E2xx/E3xx)
│   │   ├── feature_engineer.py # v1.3 特徵工程 + Device Role Aware (E6xx)
│   │   └── config_models.py    # ✅ SSOT 配置模型 (E000-E999)
│   ├── utils/                  
│   │   └── config_loader.py    # ✅ ConfigLoader (E406, 檔案鎖)
│   ├── modeling/               # [TODO] 機器學習模型
│   ├── optimization/           # 優化演算法
│   └── equipment/              # [TODO] 設備驗證
├── config/                     # 配置檔案
│   └── features/               # ✅ Feature Annotation 配置
│       ├── schema.json         # ✅ JSON Schema v1.3
│       ├── physical_types.yaml # ✅ 18+ 物理類型
│       ├── equipment_taxonomy.yaml  # ✅ 設備分類法
│       └── sites/              # ✅ 案場標註
├── tools/                      # 工具鏈
│   └── features/               # ✅ Feature Annotation 工具
│       ├── wizard.py           # ✅ Wizard CLI
│       └── excel_to_yaml.py    # ✅ 轉換器
├── tests/                      # 單元測試
│   ├── test_container_initialization.py  # ✅ 35 項測試
│   ├── test_parser_v21.py      # ✅ 16 項測試
│   ├── test_cleaner_simple.py  # ✅ 12 項測試
│   ├── test_cleaner_v22.py     # ✅ 10 項測試
│   ├── test_cleaner_equipment_validation.py  # ✅ 14 項測試
│   └── features/               # ✅ Feature Annotation 測試
│       └── test_annotation_manager.py    # ✅ 18 項測試
├── docs/                       # 專案文檔
│   ├── 專案任務排程/           # 任務排程與執行摘要
│   ├── Interface Contract/     # Interface Contract v1.1
│   ├── System Integration/     # System Integration v1.2
│   └── Feature Annotation Specification/  # Feature Annotation v1.3
└── main.py                     # CLI 主程式
```

---

## 🎯 已完成項目 (Sprint 1 - 4/4 完成)

### ✅ 1.1 Interface Contract v1.1

**完成日期**: 2026-02-19

建立完整的系統介面規範：

| 項目 | 內容 |
|:---|:---|
| **錯誤代碼體系** | E000-E999 完整定義（7 大類別） |
| **檢查點規格** | #1-#7 關鍵介面檢查點 |
| **DataFrame 介面** | timestamp (UTC/ns), quality_flags (List[str]) |
| **Header Standardization** | snake_case 正規化規則 |
| **Temporal Baseline** | E000 時間基準傳遞機制 |

**文件**: [PRD_Interface_Contract_v1.1.md](./docs/Interface%20Contract/PRD_Interface_Contract_v1.1.md)

---

### ✅ 1.2 System Integration v1.2

**完成日期**: 2026-02-19  
**測試結果**: 35 項單元測試全部通過 ✅

#### SI-001: PipelineContext

Thread-safe Singleton 時間基準管理：

```python
from src.context import PipelineContext

context = PipelineContext()
context.initialize(site_id="cgmh_ty")

# 取得時間基準（E000 檢查）
baseline = context.get_baseline()

# 未來資料檢測
is_future = context.is_future(timestamp, tolerance_minutes=5)

# 時間漂移警告（E000-W）
warning = context.check_drift_warning()
```

**錯誤代碼實作**: E000, E000-W

#### SI-002: ETLConfig (Pydantic)

型別安全的配置管理：

```python
from src.etl.config_models import ETLConfig, AnnotationConfig

# 自動驗證 physical_type、device_role
config = AnnotationConfig(
    column_name="chiller_1_power",
    physical_type="power",      # 驗證允許值
    unit="kW",
    device_role="primary"       # 驗證: primary/backup/seasonal/auxiliary/standby
)

# E405: 目標變數不可啟用 Lag（自動驗證）
```

**錯誤代碼實作**: E405, E906

#### SI-003: ConfigLoader

強化的配置載入與同步檢查：

```python
from src.utils.config_loader import ConfigLoader

loader = ConfigLoader()

# E406 同步檢查
result = loader.validate_annotation_sync("cgmh_ty")
if not result.is_synced:
    print(result.message)         # 詳細錯誤訊息
    print(result.recovery_action)  # 恢復建議

# 載入配置（含檔案鎖保護）
config = loader.load_etl_config("cgmh_ty")
```

**錯誤代碼實作**: E007, E406, E408  
**機制**: 檔案鎖、原子寫入、備份恢復

#### SI-004: ETLContainer

4 步驟初始化順序控制：

```python
from src.container import ETLContainer

# 完整初始化（依序執行 4 步驟）
container = ETLContainer(site_id="cgmh_ty", enable_sync_check=True)
container.initialize_all()

# 或逐步初始化
container.step1_create_context()      # PipelineContext
container.step2_load_config()          # ConfigLoader + ETLConfig
container.step3_load_annotation()      # FeatureAnnotationManager
container.step4_initialize_modules()   # Parser, Cleaner, etc.

# 取得元件
parser = container.get_parser()
cleaner = container.get_cleaner()
config = container.get_config()
```

**設計**: Foundation First Policy（嚴格順序控制）

#### 新增檔案

| 檔案 | 行數 | 說明 |
|:---|:---:|:---|
| `src/context.py` | 337 | PipelineContext 時間基準 |
| `src/container.py` | 543 | ETLContainer DI 容器 |
| `src/utils/config_loader.py` | 485 | ConfigLoader 強化 |
| `src/etl/config_models.py` | 1554+ | SSOT + Pydantic 模型 |
| `tests/test_container_initialization.py` | 712 | 35 項單元測試 |

---

### ✅ 1.3 Feature Annotation v1.3

**完成日期**: 2026-02-21  
**測試結果**: 18 項單元測試全部通過 ✅

#### Pydantic 模型

**ColumnAnnotation**: 欄位標註模型（含 E405 驗證）
```python
from src.features.models import ColumnAnnotation

anno = ColumnAnnotation(
    column_name="chiller_01_kw",
    physical_type="power",
    unit="kW",
    device_role="primary",
    equipment_id="CH-01",
    is_target=True,
    enable_lag=False        # E405: 目標變數禁止 Lag
)
```

**EquipmentConstraint**: 設備限制條件模型
```python
from src.features.models import EquipmentConstraint

constraint = EquipmentConstraint(
    constraint_id="chiller_pump_interlock",
    check_type="requires",
    check_phase="precheck",
    trigger_status=["chiller_01_status"],
    required_status=["chw_pri_pump_01_status"],
    error_code="E350"
)
```

#### FeatureAnnotationManager

唯讀特徵標註管理器（E500/E501 防護）：

```python
from src.features import FeatureAnnotationManager

manager = FeatureAnnotationManager("cgmh_ty")

# 基礎查詢
anno = manager.get_column_annotation("chiller_01_chwst")
role = manager.get_device_role("chiller_01_kw")        # "primary"
eq_id = manager.get_equipment_id("chiller_01_kw")      # "CH-01"

# HVAC 專用查詢
chillers = manager.get_columns_by_equipment_type("chiller")
targets = manager.get_target_columns()                  # 目標變數
constraints = manager.get_equipment_constraints(phase="precheck")

# 電力相關欄位分類
electrical = manager.get_electrical_columns()
# {"power": [...], "current": [...], "voltage": [...], "pf": [...], "energy": [...]}
```

**錯誤代碼實作**: E400, E402, E404, E405, E407, E408, E500, E501

#### Wizard CLI

互動式特徵標註工具：

```bash
python tools/features/wizard.py \
  --site cgmh_ty \
  --csv data.csv \
  --excel features.xlsx
```

**功能**:
- 自動備份（保留最近 10 個版本）
- HVAC 語意推測（依欄位名稱推測設備類型）
- Header Standardization 預覽

#### Excel 轉換器

```bash
python tools/features/excel_to_yaml.py \
  --input features.xlsx \
  --output config/features/sites/cgmh_ty.yaml
```

**功能**:
- Excel → YAML 單向轉換
- Checksum 計算（E406 同步檢查）
- HVAC 邏輯驗證

#### 新增檔案

| 檔案 | 行數 | 說明 |
|:---|:---:|:---|
| `src/features/__init__.py` | 30 | 模組初始化 |
| `src/features/models.py` | 160+ | Pydantic 模型 |
| `src/features/annotation_manager.py` | 550+ | FeatureAnnotationManager |
| `tools/features/wizard.py` | 470+ | Wizard CLI |
| `tools/features/excel_to_yaml.py` | 490+ | 轉換器 |
| `config/features/schema.json` | 250+ | JSON Schema v1.3 |
| `config/features/physical_types.yaml` | 180+ | 18+ 物理類型 |
| `config/features/equipment_taxonomy.yaml` | 150+ | 設備分類法 |
| `config/features/sites/template_factory.yaml` | 350+ | 工廠範本 |
| `tests/features/test_annotation_manager.py` | 450+ | 18 項測試 |

---

## 🎯 已完成項目 (Sprint 2 - 3/3 完成)

### ✅ 2.1 Parser v2.1

**完成日期**: 2026-02-23  
**測試結果**: 16 項單元測試全部通過 ✅  
**審查結果**: 🟢 **A級** - 全數通過，無需重工

#### 編碼自動偵測 (P-001~P-002)

```python
from src.etl.parser import ReportParser

parser = ReportParser(site_id="cgmh_ty")

# 自動偵測 UTF-8/Big5/UTF-16，處理 BOM
df = parser.parse_file("data/raw/report.csv")

# 輸出驗證：timestamp 必須為 UTC/ns
print(df.schema["timestamp"])  # Datetime(time_unit='ns', time_zone='UTC')
```

**支援編碼**: UTF-8 (含 BOM) → CP950 (Big5) → UTF-16

#### 智慧標頭搜尋 (P-003)

掃描前 500 行，支援中文標頭 (日期/時間/Date/Time)：
- 評分機制: Date+Time (+2分), DateTime (+2分), 欄位數>3 (+1分)
- 分隔符一致性驗證防止誤判

#### 時區強制轉換 (P-004)

```python
def _standardize_timezone(self, df: pl.DataFrame) -> pl.DataFrame:
    """強制輸出 Datetime(time_unit='ns', time_zone='UTC')"""
    # 情況1: 已為 UTC → 確認 time_unit
    # 情況2: 其他時區 → convert_time_zone("UTC")
    # 情況3: Naive → replace_time_zone(assumed) → convert_time_zone("UTC")
```

#### 輸出契約驗證 (P-006)

```python
def _validate_output_contract(self, df: pl.DataFrame) -> None:
    """Interface Contract v1.0 檢查點 #1"""
    # E101: BOM/Null byte 檢查
    # E102: timestamp 必須為 UTC/ns
    # E103: 必要欄位存在性
    # E104/E105: 標頭相關錯誤
```

**錯誤代碼實作**: E101, E102, E103, E104, E105

#### 新增檔案

| 檔案 | 行數 | 說明 |
|:---|:---:|:---|
| `src/etl/parser.py` | 770+ | ReportParser v2.1 主實作 |
| `tests/test_parser_v21.py` | 450+ | 16 項單元測試 |
| `config/site_templates.yaml` | 120+ | 案場配置範本 |

---

### ✅ 2.2 Cleaner v2.2

**完成日期**: 2026-02-23  
**測試結果**: 26 項單元測試全部通過 ✅ (12 基礎 + 14 設備驗證)  
**審查結果**: 🟢 **A級** - 所有問題全數關閉，具備完整生產級品質

#### Temporal Context 注入 (E000)

```python
from src.etl.cleaner import DataCleaner, CleanerConfig
from src.context import PipelineContext

# 初始化 PipelineContext（時間基準）
context = PipelineContext()
context.initialize(timestamp=datetime.now(timezone.utc))

# 初始化 Cleaner（強制要求 pipeline_context）
config = CleanerConfig()
cleaner = DataCleaner(
    config=config,
    annotation_manager=annotation_manager,
    pipeline_context=context  # E000 檢查
)
```

#### 語意感知清洗

```python
# Cleaner 內部根據 device_role 調整閾值
def _semantic_aware_cleaning(self, df, column_name):
    role = self.annotation.get_device_role(column_name)
    
    if role == "primary":
        threshold = 0.01  # 嚴格閾值
    elif role in ("backup", "seasonal"):
        threshold = 0.05  # 放寬閾值
    # ...
```

#### 設備邏輯預檢 (E350) - SSOT 驅動

```python
# 檢查設備邏輯一致性
def _apply_equipment_validation_precheck(self, df):
    # _CONSTRAINT_HANDLERS 分派表：
    # - chiller_pump_mutex: 主機開啟時水泵必須運轉
    # - pump_redundancy: 至少一台冷凍水泵和冷卻水泵運轉
    # 違規標記為 PHYSICAL_IMPOSSIBLE
    # PRECHECK_CONSTRAINTS 鍵集動態決定執行哪些 handler
```

#### 未來資料檢查 (E102) - 強化版

```python
def _check_future_data(self, df: pl.DataFrame) -> pl.DataFrame:
    """使用 pipeline_origin_timestamp 檢查，非 datetime.now()"""
    # 容忍 5 分鐘誤差
    # 新增 future_data_behavior: "reject"(default) | "filter" | "flag_only"
```

#### E500 防護 - Schema 淨化

```python
# 輸出前強制移除敏感欄位
FORBIDDEN_COLS = frozenset({
    'device_role', 'ignore_warnings', 'is_target', 'role',
    'device_type', 'annotation_role', 'col_role', 'feature_role'
})

# 確保 device_role 絕對不會洩漏到輸出
```

**錯誤代碼實作**: E000, E102, E350, E500

#### 改善計畫驗收 (10/10 項達成)

| 項目 | 改善內容 | 狀態 |
|:---:|:---|:---:|
| Phase 1-1 | quality_flags 重採樣邏輯 (`explode().unique().implode()`) | ✅ |
| Phase 1-2 | future_data_behavior 3種模式 | ✅ |
| Phase 1-3 | test_c22_ts_03 永真斷言修正 | ✅ |
| Phase 1-4 | 新增設備驗證測試檔 (370行, 14案例) | ✅ |
| Phase 2-1 | EQUIPMENT_TYPE_PATTERNS 集中管理 | ✅ |
| Phase 2-2 | 稽核軌跡時間語意區分 | ✅ |
| Phase 2-3 | 凍結偵測邊界防護 | ✅ |
| Phase 3-1 | _is_snake_case 中文前綴支援 | ✅ |
| Phase 3-2 | 測試隔離性 (reset_for_testing) | ✅ |
| Phase 3-3 | PRECHECK_CONSTRAINTS SSOT 驅動 | ✅ |

#### 新增檔案

| 檔案 | 行數 | 說明 |
|:---|:---:|:---|
| `src/etl/cleaner.py` | 1303+ | DataCleaner v2.2 主實作 |
| `tests/test_cleaner_simple.py` | 200+ | 12 項基礎單元測試 |
| `tests/test_cleaner_v22.py` | 622+ | 10 項 v2.2 功能測試 |
| `tests/test_cleaner_equipment_validation.py` | 370+ | 14 項設備驗證測試 |

---

### ✅ 2.3 BatchProcessor v1.3

**完成日期**: 2026-02-24  
**測試結果**: 32 項單元測試全部通過 ✅ (v4.0: +E201 型別驗證, +E408 SSOT 驗證)  
**審查結果**: 🟡 **A-級** - 10/10 項達成，4項 Critical/High 修復完成，1項 Medium 待修復

#### Parquet 寫入 (E206)

```python
from src.etl.batch_processor import BatchProcessor

# 初始化 BatchProcessor（強制要求 pipeline_context）
bp = BatchProcessor(
    site_id="cgmh_ty",
    output_dir="data/processed",
    pipeline_context=context  # E000 檢查
)

# 處理並輸出
df_processed = bp.process(df_cleaned)

# 輸出檔案:
# - data_batch_001.parquet (INT64 timestamp, UTC, NANOS)
# - manifest_v1.3.json
```

**強制格式**: `Datetime(time_unit='ns', time_zone='UTC')` as INT64

#### Manifest 生成 v1.3-CA

```python
@dataclass
class Manifest:
    manifest_version: str = "1.3-CA"
    temporal_baseline: TemporalBaseline
    equipment_validation_audit: EquipmentValidationAudit
    annotation_audit_trail: AnnotationAuditTrail
    ssot_snapshot: SSOTSnapshot
```

包含：
- `temporal_baseline`: 時間基準傳遞 (E000)
- `equipment_validation_audit`: 設備驗證稽核 (E351)
- `annotation_audit_trail`: 標注稽核軌跡
- `ssot_snapshot`: SSOT 版本快照 (E408)

#### 錯誤代碼實作

| 錯誤碼 | 名稱 | 說明 |
|:---:|:---|:---|
| E000 | TEMPORAL_BASELINE_MISSING | 未提供 PipelineContext |
| E202 | UNKNOWN_QUALITY_FLAG | 非法品質標記 |
| E205 | FUTURE_DATA_IN_BATCH | 批次含未來資料 |
| E206 | PARQUET_FORMAT_VIOLATION | Parquet 格式不符 |
| E351 | EQUIPMENT_VALIDATION_AUDIT_MISSING | 缺少設備驗證稽核 |
| E406 | EXCEL_YAML_OUT_OF_SYNC | Excel/YAML 不同步 |
| E408 | SSOT_QUALITY_FLAGS_MISMATCH | SSOT 版本不匹配 |
| E500 | DEVICE_ROLE_LEAKAGE | device_role 洩漏 |

#### 新增檔案

| 檔案 | 行數 | 說明 |
|:---|:---:|:---|
| `src/etl/batch_processor.py` | 825+ | BatchProcessor v1.3 主實作 |
| `src/etl/manifest.py` | 250+ | Manifest Pydantic 模型 |
| `tests/test_batch_processor_v13.py` | 867+ | 32 項單元測試 |

---

### ✅ 2.4 Sprint 2 Demo 展示

**完成日期**: 2026-02-24  
**展示頁面**: `tools/demo/sprint2_etl.html`

#### 展示內容

| 任務 ID | 內容 | 技術實現 |
|:---|:---|:---|
| DEMO-201 | ETL 三階段流程動畫 | CSS Animation |
| DEMO-202 | 輸入/輸出 DataFrame 對比 | Before/After 表格 |
| DEMO-203 | 品質檢查雷達圖 | Chart.js Radar |
| DEMO-204 | 設備邏輯預檢結果 | E350 違規案例 |
| DEMO-205 | Manifest 輸出展示 | YAML Viewer |

#### 開啟方式

```bash
cd tools/demo
python -m http.server 8080
# 瀏覽器開啟 http://localhost:8080
```

---

## 🚀 使用指南

### 快速開始

```python
from src.container import ETLContainer

# 初始化 HVAC 服務（自動執行 4 步驟初始化）
container = ETLContainer(site_id="cgmh_ty")
container.initialize_all()

# 取得時間基準
baseline = container.get_temporal_baseline()

# 取得配置
config = container.get_config()

# 取得 FeatureAnnotationManager
from src.features import FeatureAnnotationManager
manager = FeatureAnnotationManager("cgmh_ty")
```

### 使用 FeatureAnnotationManager

```python
from src.features import FeatureAnnotationManager

manager = FeatureAnnotationManager("cgmh_ty")

# 查詢設備角色（供 Cleaner 使用）
role = manager.get_device_role("chiller_01_kw")

# 查詢設備限制（供 Optimization 使用）
constraints = manager.get_equipment_constraints(phase="precheck")

# 查詢目標變數
targets = manager.get_target_columns()
```

### 使用 Parser v2.1

```python
from src.etl.parser import ReportParser

# 初始化 Parser（使用案場配置）
parser = ReportParser(site_id="cgmh_ty")

# 解析 CSV 檔案
df = parser.parse_file("data/raw/report.csv")

# 輸出驗證：timestamp 必須為 UTC/ns
print(df.schema["timestamp"])  # Datetime(time_unit='ns', time_zone='UTC')

# 解析並取得中繼資料
df, metadata = parser.parse_with_metadata("data/raw/report.csv")
print(metadata["detected_encoding"])  # utf-8 / cp950 / utf-16
print(metadata["header_line"])        # 標頭行號
```

### 使用 Cleaner v2.2

```python
from src.etl.cleaner import DataCleaner, CleanerConfig
from src.context import PipelineContext
from src.features import FeatureAnnotationManager

# 初始化 PipelineContext
context = PipelineContext()
context.initialize(timestamp=datetime.now(timezone.utc))

# 初始化 FeatureAnnotationManager
annotation_manager = FeatureAnnotationManager("cgmh_ty")

# 初始化 Cleaner
config = CleanerConfig(
    future_data_behavior="reject",  # "reject" | "filter" | "flag_only"
    frozen_data_min_periods=1
)
cleaner = DataCleaner(
    config=config,
    annotation_manager=annotation_manager,
    pipeline_context=context  # E000 檢查
)

# 清洗資料
df_cleaned = cleaner.clean(df)
```

### CLI 執行

```bash
# 執行完整 Pipeline（將遵循 v1.3 初始化順序）
python main.py pipeline data/raw/report.csv --site cgmh_ty

# 使用 Wizard 建立標註
python tools/features/wizard.py --site cgmh_ty --csv data.csv --excel features.xlsx

# 轉換 Excel 至 YAML
python tools/features/excel_to_yaml.py --input features.xlsx
```

### 啟動 Demo 展示頁面

由於展示頁面包含本地 JSON 動態載入，直接點擊 HTML 會有 CORS 限制。請使用以下指令啟動：

```bash
cd tools/demo
python -m http.server 8080
# 接著在瀏覽器開啟: http://localhost:8080/index.html
```

### 啟動互動式測試工具 (Sprint 2)

本專案提供了一個完整三步互動式測試工具，涵蓋「產生標註 Excel」、「轉換 YAML」、「執行批次管線」。
**v1.3 新增功能**: 支援多檔/資料夾上傳、階段性診斷工具 (Parser/Cleaner 獨立測試)、清洗與重採樣間隔設定下拉選單、Chaos Testing 防禦驗證機制、以及 parquet 檔案直連下載功能。
詳細說明與變更紀錄請參閱：**[Interactive ETL Tester 說明文件](docs/測試工具說明/Interactive_ETL_Tester.md)**

若要啟動互動式測試工具：

1. 啟動後端 API (FastAPI):
```bash
pip install fastapi uvicorn python-multipart
uvicorn tools.demo.test_server:app --reload --port 8000
```
2. 在瀏覽器點擊或雙擊開啟 `tools/demo/tester.html`，即可使用圖形化介面。

---

## 🧪 測試

### 執行測試

```bash
# 執行 System Integration 測試
python3 -m pytest tests/test_container_initialization.py -v

# 執行 Feature Annotation 測試
python3 -m pytest tests/features/test_annotation_manager.py -v

# 執行 Parser v2.1 測試
python3 -m pytest tests/test_parser_v21.py -v

# 執行 Cleaner v2.2 測試
python3 -m pytest tests/test_cleaner_simple.py -v
python3 -m pytest tests/test_cleaner_v22.py -v
python3 -m pytest tests/test_cleaner_equipment_validation.py -v

# 執行 BatchProcessor v1.3 測試
python3 -m pytest tests/test_batch_processor_v13.py -v

# 執行全部測試
python3 -m pytest tests/ -v

# 預期結果: 122+ passed (Sprint 1: 53 + Sprint 2: 69)
```

### 測試覆蓋

| 類別 | 測試數 | 說明 |
|:---|:---:|:---|
| PipelineContext | 9 | 單例、E000、時間漂移、執行緒安全 |
| ETLConfig | 6 | Pydantic、E405、版本相容性 |
| ConfigLoader | 7 | E406、E007、檔案鎖 |
| ETLContainer | 7 | 4 步驟初始化順序 |
| 時間基準傳遞 | 6 | 跨日、注入、驗證 |
| FeatureAnnotationManager | 14 | 初始化、查詢、HVAC、錯誤 |
| Pydantic 模型 | 4 | E405、Lag 間隔、命名 |
| Parser v2.1 | 16 | 編碼、時區、標頭、契約驗證 |
| Cleaner v2.2 | 26 | E000、E102、E350、E500、設備驗證 |
| BatchProcessor v1.3 | 32 | E000、E201、E206、E351、E408、Manifest |
| **總計** | **127** | **Sprint 1: 53 + Sprint 2: 74** |

---

## 📚 專案文檔

### 核心架構規範

- **[Interface Contract v1.1](docs/Interface%20Contract/PRD_Interface_Contract_v1.1.md)** ⭐ 
  - 10 個檢查點定義 (E000 時間基準 → E901 特徵對齊)
  - 100+ 錯誤代碼體系 (E000-E999)
  - Temporal Baseline 時間基準規範

- **[System Integration v1.2](docs/System%20Integration/PRD_System_Integration_v1.2.md)** ⭐
  - 系統整合架構與 4 步驟初始化順序
  - Foundation First Policy
  - Container 依賴注入機制

- **[Feature Annotation v1.3](docs/Feature%20Annotation%20Specification/PRD_Feature_Annotation_Specification_V1.3.md)** ⭐ **(New!)**
  - 特徵標註系統規範
  - HVAC 設備限制條件
  - Excel ↔ YAML 單向同步

### 任務排程與執行摘要

- **[專案任務排程](docs/專案任務排程/專案任務排程文件.md)** - 完整 Sprint 規劃
- **[Sprint 1 執行摘要](docs/專案任務排程/Sprint_1_執行摘要.md)** - Interface Contract、System Integration、Feature Annotation 詳細摘要
- **[Sprint 1 審查報告](docs/專案任務排程/Sprint_1_Review_Report.md)** - Sprint 1 審查詳情
- **[Sprint 2 執行摘要](docs/專案任務排程/Sprint_2_執行摘要.md)** - Parser v2.1 & Cleaner v2.2 詳細摘要
- **[Sprint 2 審查報告](docs/專案任務排程/Sprint_2_Review_Report.md)** - Parser v2.1 & Cleaner v2.2 審查詳情

### ETL 管道模組

- **[Parser v2.1](docs/parser/PRD_Parser_V2.1.md)** ✅ - Header Standardization、UTC/ns 時間戳、編碼自動偵測
- **[Cleaner v2.2](docs/cleaner/PRD_CLEANER_v2.2.md)** ✅ - 語意感知清洗、Equipment Precheck、SSOT 驅動
- **[BatchProcessor v1.3](docs/batch_processor/PRD_BATCH_PROCESSOR_v1.3.md)** - Manifest 生成、E406 驗證

### 機器學習與最佳化

- **[Model Training v1.3](docs/Model_Training/PRD_Model_Training_v1.3.md)** - 三種訓練模式、Resource-Aware Training
- **[Optimization Engine v1.2](docs/Chiller_Plant_Optimization_Engine/PRD_Chiller_Plant_Optimization_V1.2.md)** - 黑盒優化、Fallback 機制

### Web 應用層 (Frontend & Backend Interface)

- **[Web 應用層架構與 API 介面規範 v1.1](docs/Web_Application_Layer/PRD_Web_Application_Architecture_V1.1.md)** - 系統架構邊界與前後端解耦
- **[Web API 介面規格設計 v1.1](docs/Web_Application_Layer/PRD_Web_API_Interface_V1.1.md)** - RESTful API 與 WebSocket 介面規範
- **[Web UI 前端頁面流程與狀態圖 v1.1](docs/Web_Application_Layer/PRD_UI_Flow_and_State_V1.1.md)** - 前端頁面結構與狀態轉換

---

## 🚧 實作路徑 (Implementation Roadmap)

### 當前狀態: Sprint 2 已完成 (3/3 完成)

```
Sprint 1: Foundation ✅ 完成
├── ✅ Interface Contract v1.1 (已完成)
│   ├── E000-E999 錯誤代碼定義
│   ├── 7 個檢查點規格
│   └── Header Standardization 規則
│
├── ✅ System Integration v1.2 (已完成)
│   ├── PipelineContext (E000 時間基準)
│   ├── ETLConfig (Pydantic 模型)
│   ├── ConfigLoader (E406 同步檢查)
│   └── ETLContainer (4步驟初始化)
│
├── ✅ Feature Annotation v1.3 (已完成)
│   ├── Pydantic 模型 (ColumnAnnotation, EquipmentConstraint)
│   ├── FeatureAnnotationManager (唯讀介面、HVAC 查詢)
│   ├── Excel 工具鏈 (Wizard、excel_to_yaml)
│   └── HVAC 設備限制條件
│
├── ✅ 程式碼審查優化 (已完成)
│   ├── Lazy Import 移除 (支援靜態分析)
│   └── STRICT_MODE 環境變數 (生產安全)
│
└── ✅ Sprint 1 Demo 展示 (已完成)
    ├── 系統架構圖 (Mermaid.js，Sprint 1 邊界高亮)
    ├── 錯誤代碼體系互動表格 (即時搜尋/過濾/設計動機)
    ├── Feature Annotation 依賴與前後比較 (Before/After)
    └── 4步驟初始化流程與測試覆蓋率分析 (Chart.js)

Sprint 2: 核心 ETL ✅ 已完成 (3/3 完成)
├── ✅ Parser v2.1 (已完成，A級)
│   ├── 編碼自動偵測 (UTF-8/Big5/UTF-16)
│   ├── BOM 處理與移除
│   ├── 智慧標頭搜尋 (中文標頭支援)
│   ├── 時區強制轉換 (→ UTC/ns)
│   └── 輸出契約驗證 (E101-E105)
├── ✅ Cleaner v2.2 (已完成，A級)
│   ├── Temporal Context 注入 (E000)
│   ├── FeatureAnnotationManager 整合
│   ├── 語意感知清洗 (device_role)
│   ├── 設備邏輯預檢 (E350，SSOT 驅動)
│   ├── 未來資料檢查 (E102，3種模式)
│   └── Schema 淨化 (E500 防護)
├── ✅ BatchProcessor v1.3 (已完成)
│   ├── Parquet 寫入 (INT64/UTC/NANOS，E206)
│   ├── Manifest 生成 (v1.3-CA)
│   ├── 設備稽核軌跡傳遞 (E351)
│   ├── E408 SSOT 版本檢查
│   └── 事務性輸出 (Staging → Output)
└── ✅ Sprint 2 Demo (已完成)
    ├── ETL 三階段流程動畫
    ├── 品質指標雷達圖 (Chart.js)
    ├── 設備邏輯違規案例展示
    └── Manifest 輸出結構展示
```

### 下一步

1. ✅ **Sprint 2: 核心 ETL** 已完成（Parser A級, Cleaner A級, BatchProcessor A-級）
2. 🚀 **準備進入 Sprint 3**: 特徵工程與模型訓練
   - Feature Engineer v1.3 (5-6天)
   - Model Training v1.3 (10-12天)

### 進入 Sprint 3 前決策點

| 決策 | 條件 | 當前狀態 |
|:---|:---|:---:|
| 允許進入 Sprint 3 | BatchProcessor 問題修復 | ✅ **已通過** |
| Feature Engineer 銜接 | BP v1.3 輸出格式穩定且 E408 有效 | ✅ **已確認** |
| CI/CD 品質門禁 | 全部 127 項測試通過 | ✅ **通過** |

### 生產環境配置

**STRICT_MODE 環境變數:**
```bash
# 開發環境（預設）- E406 僅記錄警告
python main.py pipeline data.csv

# 生產環境 - E406 檢查失敗時中斷管線
HVAC_STRICT_MODE=true python main.py pipeline data.csv
```

當 `HVAC_STRICT_MODE=true` 時，E406 Excel/YAML 同步檢查失敗會拋出 `RuntimeError` 中斷管線，確保生產環境資料一致性。

---

## 🤝 貢獻指南

請務必先閱讀以下核心文檔：
- **[Interface Contract v1.1](docs/Interface%20Contract/PRD_Interface_Contract_v1.1.md)** - 錯誤代碼規範與檢查點定義
- **[Sprint 1 執行摘要](docs/專案任務排程/Sprint_1_執行摘要.md)** - 已完成的基礎設施說明
- **[Sprint 2 執行摘要](docs/專案任務排程/Sprint_2_執行摘要.md)** - Parser v2.1 & Cleaner v2.2 詳細說明
- **[Sprint 2 審查報告](docs/專案任務排程/Sprint_2_Review_Report.md)** - 審查詳情與下游預警

確保所有新代碼遵守：
1. **Foundation First Policy** - 按照 Sprint 順序實施
2. **錯誤代碼規範** - 使用 E000-E999 錯誤代碼體系
3. **Temporal Baseline** - 禁止使用 `datetime.now()`，必須使用 PipelineContext
4. **職責分離** - Cleaner 不傳遞 `device_role`，Feature Engineer 直接查詢 Annotation
5. **唯讀防護** - 禁止直接修改 YAML，必須透過 Excel → excel_to_yaml.py 流程

---

## 📖 延伸閱讀

- [專案任務排程](docs/專案任務排程/專案任務排程文件.md) - 系統架構、風險評估、實施建議
- [Sprint 1 執行摘要](docs/專案任務排程/Sprint_1_執行摘要.md) - 詳細的完成項目與測試報告
- [Sprint 1 審查報告](docs/專案任務排程/Sprint_1_Review_Report.md) - 審查結論與優化項目
- [Sprint 2 執行摘要](docs/專案任務排程/Sprint_2_執行摘要.md) - Parser v2.1 & Cleaner v2.2 詳細摘要
- [Sprint 2 審查報告](docs/專案任務排程/Sprint_2_Review_Report.md) - 審查結論與下游預警
- [Feature Annotation 實作摘要](docs/Feature%20Annotation%20Specification/IMPLEMENTATION_SUMMARY.md) - Feature Annotation v1.3 詳細實作說明

---

**最後更新**: 2026-02-24  
**架構版本**: v1.5  
**文件狀態**: ✅ Sprint 2 已完成 (3/3 完成，Parser 🟢 A級, Cleaner 🟢 A級, BatchProcessor 🟡 A-級)
