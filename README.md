# HVAC Analytics - Core Engine (v2.1 Architecture with Phase 0 Retrofit)

**核心引擎狀態**: 🔄 **Phase 0 Retrofit 進行中 - v1.4 拓樸感知與持續學習準備**  
**審查報告**: [Sprint 2 Review Report](docs/專案任務排程/Sprint_2_Review_Report.md) - Parser v2.1 (A級), Cleaner v2.2 (A級), BatchProcessor v1.3 (A-級)；Parser v2.2 模組化驗收完成  
**Parser V2.2**: ✅ **已完成** - 模組化 Strategy Pattern 架構已上線，支援多格式 CSV + Siemens Scheduler  
**Interactive ETL Tester V1.5**: ✅ **已完成** - Step 1→2 無縫整合，欄位名稱一致性保證  
**🆕 Phase 0 Retrofit**: ⏳ **待開始** - 錯誤代碼重分配 (IC-R01~R05) + ETL 管線拓樸貫通 (P-R01, C-R01, BP-R01)  
**🆕 Feature Annotation v1.4**: ✅ **PRD 已完成** - 拓樸感知 (Topology Awareness) + 控制語意 (Control Semantics)  
**🆕 Feature Engineer v1.4**: ⏳ **Sprint 3 待開發** - 拓樸聚合特徵 (L2) + GNN 上下文輸出  
**🆕 Model Training v1.4**: ⏳ **Sprint 3 待開發** - GNN 訓練器 + Physics-Informed Hybrid Loss  
**🆕 Continual Learning v1.1**: ⏳ **Sprint 4 待開發** - Layer-wise GEM + Drift Detection + RedisLock  
**🆕 Interface Contract v1.2**: ✅ **PRD 已完成** - 擴充錯誤代碼分層 (E750-E759 GNN, E800-E829 CL, E840-E859 OPT)  
**最後更新**: 2026-02-26

---

## 📊 專案進度總覽

| 階段 | 任務 | 狀態 | 測試/展示 |
|:---:|:---|:---:|:---:|
| 1 | 1.1 Interface Contract v1.2 | ✅ 已完成 | PRD 已審查 |
| 1 | 1.2 System Integration v1.2 | ✅ 已完成 | 35/35 通過 |
| 1 | 1.3 Feature Annotation v1.4 | ✅ PRD 完成 | 拓樸感知 + 控制語意 |
| 1 | 1.4 程式碼審查優化 | ✅ 已完成 | 72/72 通過 |
| 1 | **1.5 Sprint 1 Demo 展示** | ✅ **已完成** | **[🎨 查看 Demo](tools/demo/index.html)** |
| 2 | 2.1 Parser v2.1 | ✅ **已完成** | 16/16 通過 🟢 A級 |
| 2 | 2.1.1 Parser v2.2 模組化重構 | ✅ **已完成** | 29/29 通過（含 v2.1 回歸） |
| 2 | 2.2 Cleaner v2.2 | ✅ **已完成** | 26/26 通過 🟢 A級 |
| 2 | 2.3 BatchProcessor v1.3 | ✅ **已完成** | 32/32 通過 🟡 A-級 |
| 2 | 2.4 Interactive ETL Tester v1.5 | ✅ **已完成** | Step 1→2 整合 |
| **0** | **Phase 0: v1.4 Retrofit** | ⏳ **待開始** | 錯誤代碼重分配 + ETL 拓樸貫通 |
| **3** | **3.1 Feature Engineer v1.4** | ⏳ **Sprint 3 待開發** | L2/L3 分層特徵 + GNN 輸出 |
| **3** | **3.2 Model Training v1.4** | ⏳ **Sprint 3 待開發** | GNN + Physics Loss |
| **3** | **3.3 Continual Learning v1.1** | ⏳ **Sprint 4 待開發** | Layer-wise GEM + RedisLock |
| **3** | **3.4 Optimization v1.2** | ⏳ **Sprint 4 待開發** | Fallback + CL 整合 |

**Sprint 1 總計**: 53 項測試全部通過 ✅  
**Sprint 2 總計**: 87 項測試全部通過 ✅  
**Phase 0 預計**: IC-R01~R05, FA-R01~R03, P-R01, C-R01, BP-R01  
**累計測試**: 140+ 項全部通過 ✅  
**狀態**: Sprint 1-2 完成 → **Phase 0 Retrofit** → Sprint 3-5 開發

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

## 📁 專案結構 (v1.6)

```
HVAC_Analytics/
├── src/                        # 核心源碼
│   ├── container.py            # ✅ ETLContainer (4步驟初始化)
│   ├── context.py              # ✅ PipelineContext (時間基準)
│   ├── exceptions.py           # ✅ 自定義異常類別
│   ├── features/               # ✅ Feature Annotation v1.3
│   │   ├── __init__.py
│   │   ├── models.py           # ✅ Pydantic 模型
│   │   └── annotation_manager.py  # ✅ FeatureAnnotationManager
│   ├── interface.py            # ★ Facade - 後端整合入口
│   ├── schemas.py              # Pydantic I/O 定義
│   ├── etl/                    # ETL 管道
│   │   ├── parser/             # ✅ Parser V2.2 模組化 (Strategy Pattern)
│   │   │   ├── __init__.py     # ParserFactory + get_parser() + ReportParser Facade
│   │   │   ├── base.py         # BaseParser 抽象基類
│   │   │   ├── generic_parser.py # GenericParser (V2.1 相容)
│   │   │   ├── exceptions.py   # Parser 專用錯誤定義
│   │   │   ├── utils.py        # 站點設定載入/共用工具
│   │   │   └── siemens/
│   │   │       ├── point_mapping.py
│   │   │       └── scheduler_report.py  # SiemensSchedulerReportParser
│   │   ├── parser.py           # ✅ v2.2 相容 shim (re-export，保留舊入口)
│   │   ├── cleaner.py          # ✅ v2.2 資料清洗 + Equipment Precheck (E2xx/E3xx/E5xx)
│   │   ├── batch_processor.py  # ✅ v1.3 批次處理 + Manifest (E2xx/E3xx)
│   │   ├── manifest.py         # ✅ v1.3 Manifest 模型
│   │   ├── feature_engineer.py # v1.3 特徵工程 + Device Role Aware (E6xx)
│   │   └── config_models.py    # ✅ SSOT 配置模型 (E000-E999)
│   ├── utils/                  
│   │   └── config_loader.py    # ✅ ConfigLoader (E406, 檔案鎖)
│   ├── modeling/               # [TODO] 機器學習模型
│   ├── optimization/           # 優化演算法
│   └── equipment/              # [TODO] 設備驗證
├── config/                     # 配置檔案
│   ├── site_templates.yaml     # ✅ Parser 案場範本
│   └── features/               # ✅ Feature Annotation 配置
│       ├── schema.json         # ✅ JSON Schema v1.3
│       ├── physical_types.yaml # ✅ 18+ 物理類型
│       ├── equipment_taxonomy.yaml  # ✅ 設備分類法
│       └── sites/              # ✅ 案場標註
├── tools/                      # 工具鏈
│   ├── demo/                   # ✅ Sprint 1 & 2 展示 / 互動測試UI
│   │   ├── tester.html         # ✅ ETL 測試網頁介面
│   │   └── test_server.py      # ✅ ETL 測試後端 API
│   └── features/               # ✅ Feature Annotation 工具
│       ├── wizard.py           # ✅ Wizard CLI
│       └── excel_to_yaml.py    # ✅ 轉換器
├── tests/                      # 單元測試
│   ├── test_container_initialization.py  # ✅ 35 項測試
│   ├── test_parser_v21.py      # ✅ 16 項測試
│   ├── parser/                 # ✅ Parser v2.2 模組化測試
│   │   ├── test_base.py
│   │   ├── test_factory.py
│   │   ├── test_siemens_scheduler.py
│   │   └── test_integration.py
│   ├── test_cleaner_simple.py  # ✅ 12 項測試
│   ├── test_cleaner_v22.py     # ✅ 10 項測試
│   ├── test_cleaner_equipment_validation.py  # ✅ 14 項測試
│   ├── test_batch_processor_v13.py # ✅ 32 項測試
│   └── features/               # ✅ Feature Annotation 測試
│       └── test_annotation_manager.py    # ✅ 18 項測試
├── docs/                       # 專案文檔
│   ├── 專案任務排程/           # 任務排程與執行摘要
│   ├── 測試工具說明/           # ✅ 互動測試工具說明
│   ├── Interface Contract/     # 🆕 Interface Contract v1.2 (v1.4 相容)
│   ├── System Integration/     # System Integration v1.2
│   ├── Feature Annotation Specification/  # 🆕 Feature Annotation v1.4 (拓樸感知)
│   ├── feature_engineering/    # 🆕 Feature Engineer v1.4 (L2/L3 特徵)
│   ├── Model_Training/         # 🆕 Model Training v1.4 (GNN)
│   ├── Continual_Learning/     # 🆕 Continual Learning v1.1 (GEM)
│   └── 參考資料/               # v1.4 升級藍圖參考文件
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

## 🎯 已完成項目 (Sprint 2 - 4/4 完成)

### ✅ 2.1 Parser v2.1

**完成日期**: 2026-02-23  
**測試結果**: 16 項單元測試全部通過 ✅  
**審查結果**: 🟢 **A級** - 全數通過，無需重工

> Parser V2.1 已保留為 `GenericParser` 相容策略，並由 `ReportParser` facade 與 `src/etl/parser.py` shim 維持舊入口相容。

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

### ✅ 2.1.1 Parser v2.2 模組化重構

**完成日期**: 2026-02-25  
**測試結果**: 29 項測試全部通過（含 `tests/test_parser_v21.py` 回歸）✅  
**覆蓋率**: `src/etl/parser` = **84%**  
**驗收結果**: ✅ Strategy Pattern、Siemens Scheduler、相容層、Container 整合全數完成

#### V2.2 架構與能力

```python
from src.etl.parser import ParserFactory, get_parser

# 明確指定策略
parser = ParserFactory.create_parser("siemens_scheduler")
df = parser.parse_file("siemens_report.csv")

# 自動偵測策略
auto_parser = get_parser("auto", file_path="data/raw/report.csv")
df_auto = auto_parser.parse_file("data/raw/report.csv")
```

- 支援策略：`generic`、`siemens_scheduler`、`auto`
- `ParserFactory.auto_detect()` 可辨識 Siemens 報表，未知格式 fallback `generic`
- `ReportParser` facade + `src/etl/parser.py` shim 保持 v2.1 舊入口可用
- 新增 API：`/api/v1/parser/strategies`、`/api/v1/pipeline/parse-preview`

#### Siemens Scheduler 支援

```python
parser = ParserFactory.create_parser("siemens_scheduler")
df = parser.parse_file("report.csv")
metadata = parser.get_metadata()

print(df.columns)               # ["timestamp", "ahwp_3_kwh", ...]
print(metadata["point_mapping"])  # {"point_1": {...}, "point_2": {...}}
```

#### 新增檔案（已完成）

| 檔案 | 說明 |
|:---|:---|
| `src/etl/parser/__init__.py` | Factory + facade + auto detect |
| `src/etl/parser/base.py` | BaseParser 抽象介面 |
| `src/etl/parser/generic_parser.py` | GenericParser（v2.1 相容） |
| `src/etl/parser/siemens/point_mapping.py` | Siemens 點位映射 |
| `src/etl/parser/siemens/scheduler_report.py` | Siemens Scheduler 解析器 |
| `src/etl/parser/utils.py` | 設定載入與共用函式 |
| `src/etl/parser.py` | 相容 shim（re-export v2.2 API） |
| `tests/parser/test_base.py` | BaseParser 測試 |
| `tests/parser/test_factory.py` | Factory/auto_detect 測試 |
| `tests/parser/test_siemens_scheduler.py` | Siemens 測試 |
| `tests/parser/test_integration.py` | Parser→Cleaner 整合測試 |
| `docs/parser/MIGRATION_v2.1_to_v2.2.md` | v2.1→v2.2 遷移指南 |

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

### ✅ 2.4 Interactive ETL Tester v1.5

**完成日期**: 2026-02-25  
**文件**: [Interactive ETL Tester 說明](docs/測試工具說明/Interactive_ETL_Tester.md)

#### Step 1→2 整合流程（核心改進）

```
Step 1: Parser Preview ───────┐
    │                         │
    ▼                         │
顯示 columns + point_mapping   │
    │                         │
    ▼                         ▼
點擊「從預覽結果產生」  →  Step 2: Excel 標註範本
    │                         │
    ▼                         ▼
欄位名稱完全一致 ←────────────┘
(確保與 Step 4 ETL Pipeline 相容)
```

#### 關鍵功能

| 功能 | 說明 | 驗收標準 |
|:---|:---|:---|
| **無縫整合** | Step 1 預覽後直接產生 Excel，無需重新上傳 CSV | ✅ 完成 |
| **欄位一致性** | Excel `column_name` 顯示 Parser 標準化後的 snake_case | ✅ 完成 |
| **點位映射** | Excel `description` 顯示 `[Point_X \| 原始名稱]` 對照 | ✅ 完成 |
| **E409 預防** | Step 1→Step 4 欄位名稱完全一致，避免 Header Mismatch | ✅ 完成 |

#### API 端點

- `POST /api/v1/pipeline/parse-preview` - Step 1: Parser 預覽（回傳 columns, point_mapping）
- `POST /api/generate-template-from-preview` - Step 2: 從預覽結果產生 Excel

#### 程式碼範例

```python
# Step 1: 預覽解析
from src.etl.parser import get_parser
parser = get_parser("auto", file_path="report.csv")
df = parser.parse_file("report.csv")
metadata = parser.get_metadata()
# metadata["columns"] = ["timestamp", "ahwp_3_kwh", ...]
# metadata["point_mapping"] = {"point_1": {"name": "AHWP-3.KWH", ...}}

# Step 2: 直接從預覽結果產生 Excel（不重新讀取 CSV）
from tools.features.wizard import FeatureAnnotationWizard
wizard = FeatureAnnotationWizard(site_id="demo")
wizard.run_from_parser_result(
    columns=metadata["columns"],
    point_mapping=metadata["point_mapping"],
    sample_data=df.head(10).to_dicts()
)
# 輸出: demo_features.xlsx
# - column_name: "ahwp_3_kwh" (snake_case)
# - description: "[Point_1 | AHWP-3.KWH]"
```

---

### ✅ 2.5 Sprint 2 Demo 展示

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

### 使用 Parser v2.1/v2.2

```python
# === V2.1 方式（維護模式，保持向後相容）===
from src.etl.parser import ReportParser

parser = ReportParser(site_id="cgmh_ty")
df = parser.parse_file("data/raw/report.csv")

# === V2.2 方式（推薦新專案使用）===
from src.etl.parser import ParserFactory, get_parser

# 方式 1: 自動偵測最佳 Parser
parser = get_parser("auto", file_path="data/raw/report.csv")
df = parser.parse_file("data/raw/report.csv")

# 方式 2: 明確指定 Parser 類型
parser = ParserFactory.create_parser("siemens_scheduler")
df = parser.parse_file("siemens_report.csv")

# 取得解析元資料
metadata = parser.get_metadata()
print(metadata["source_format"])      # "siemens_scheduler"
print(metadata["header_line"])        # 127
print(metadata["point_mapping"])      # {"point_1": "ahwp_3_kwh", ...}

# 輸出驗證：所有 Parser 統一輸出 UTC/ns 時間戳
print(df.schema["timestamp"])  # Datetime(time_unit='ns', time_zone='UTC')
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

本專案提供了一個完整四步互動式測試工具，涵蓋「Parser 預覽」、「產生標註 Excel」、「轉換 YAML」、「執行批次管線」。

**v1.5 新增功能 (Step 1→2 整合)**: 
- Step 1 預覽 Parser 結果後，可直接點擊「從預覽結果產生 Excel」按鈕
- **無需重新上傳 CSV**，確保欄位名稱從 Step 1 到 Step 4 完全一致
- Excel `column_name` 顯示 Parser 標準化後的 snake_case 名稱（如 `ahwp_3_kwh`）
- Excel `description` 顯示 Point 映射資訊（如 `[Point_1 | AHWP-3.KWH]`）
- **預防 E409 (Header Annotation Mismatch)**：Step 1→Step 4 欄位名稱完全一致

**v1.3 功能**: 支援多檔/資料夾上傳、階段性診斷工具 (Parser/Cleaner 獨立測試)、清洗與重採樣間隔設定下拉選單、Chaos Testing 防禦驗證機制、以及 parquet 檔案直連下載功能。

詳細說明與變更紀錄請參閱：**[Interactive ETL Tester 說明文件](docs/測試工具說明/Interactive_ETL_Tester.md)**

#### 快速開始

```bash
# 1. 啟動後端 API (FastAPI)
pip install fastapi uvicorn python-multipart
uvicorn tools.demo.test_server:app --reload --port 8000 --host 0.0.0.0

# 2. 在瀏覽器開啟 tester.html
tools/demo/tester.html
```

#### 推薦工作流程 (v1.5)

```
Step 1: 上傳 CSV → 選擇 Parser → 預覽解析
              ↓
      點擊「從預覽結果產生 Excel」
              ↓
Step 2: 自動下載 Excel（欄位名稱已標準化）
              ↓
Step 3: 填寫 Excel → 上傳轉換為 YAML
              ↓
Step 4: 執行完整 ETL Pipeline
```

**關鍵優勢**: Step 1 預覽時已將 CSV 欄位名稱標準化為 snake_case，Step 2 產生的 Excel 直接使用這些標準化名稱，確保與 Step 4 ETL Pipeline 輸出完全一致，避免欄位名稱不匹配問題。

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

# 執行 Parser v2.2 模組化測試（含回歸）
python3 -m pytest tests/parser tests/test_parser_v21.py -v

# 執行 Cleaner v2.2 測試
python3 -m pytest tests/test_cleaner_simple.py -v
python3 -m pytest tests/test_cleaner_v22.py -v
python3 -m pytest tests/test_cleaner_equipment_validation.py -v

# 執行 BatchProcessor v1.3 測試
python3 -m pytest tests/test_batch_processor_v13.py -v

# 執行全部測試
python3 -m pytest tests/ -v

# 預期結果: 140+ passed (Sprint 1: 53 + Sprint 2: 87)
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
| Parser v2.2 (含 v2.1 回歸) | 29 | Factory、Siemens、相容層、回歸驗證 |
| Cleaner v2.2 | 26 | E000、E102、E350、E500、設備驗證 |
| BatchProcessor v1.3 | 32 | E000、E201、E206、E351、E408、Manifest |
| **總計** | **140** | **Sprint 1: 53 + Sprint 2: 87** |

---

## 📚 專案文檔

### 核心架構規範

- **[Interface Contract v1.2](docs/Interface%20Contract/PRD_Interface_Contract_v1.2.md)** ⭐ **(New!)**
  - 10 個檢查點定義 (E000 時間基準 → E901 特徵對齊)
  - 100+ 錯誤代碼體系 (E000-E999) - **新增 E750-E759 (GNN), E800-E829 (CL), E840-E859 (OPT)**
  - Temporal Baseline 時間基準規範
  - **v1.4 拓樸感知與持續學習相容性**

- **[System Integration v1.2](docs/System%20Integration/PRD_System_Integration_v1.2.md)** ⭐
  - 系統整合架構與 4 步驟初始化順序
  - Foundation First Policy
  - Container 依賴注入機制

- **[Feature Annotation v1.4](docs/Feature%20Annotation%20Specification/PRD_Feature_Annotation_Specification_V1.4.md)** ⭐ **(New!)**
  - **拓樸感知 (Topology Awareness)** - Graph 節點/邊緣定義
  - **控制語意 (Control Semantics)** - Decay factor 與控制策略
  - HVAC 設備限制條件
  - Excel ↔ YAML 單向同步

### 任務排程與執行摘要

- **[專案任務排程](docs/專案任務排程/專案任務排程文件.md)** - 完整 Sprint 規劃
- **[Sprint 1 執行摘要](docs/專案任務排程/Sprint_1_執行摘要.md)** - Interface Contract、System Integration、Feature Annotation 詳細摘要
- **[Sprint 1 審查報告](docs/專案任務排程/Sprint_1_Review_Report.md)** - Sprint 1 審查詳情
- **[Sprint 2 執行摘要](docs/專案任務排程/Sprint_2_執行摘要.md)** - Parser v2.1 + v2.2、Cleaner v2.2、BatchProcessor v1.3 詳細摘要
- **[Sprint 2 審查報告](docs/專案任務排程/Sprint_2_Review_Report.md)** - Parser v2.1、Cleaner v2.2、BatchProcessor v1.3 審查詳情

### ETL 管道模組

- **[Parser v2.1](docs/parser/_archive/PRD_Parser_V2.1.md)** ✅ - Header Standardization、UTC/ns 時間戳、編碼自動偵測
- **[Parser v2.2](docs/parser/PRD_Parser_V2.2.md)** ✅ - Strategy Pattern 模組化架構、Siemens Scheduler、多格式支援
- **[Parser v2.2 Migration](docs/parser/MIGRATION_v2.1_to_v2.2.md)** ✅ - 舊入口相容與遷移指南
- **[Cleaner v2.2](docs/cleaner/PRD_CLEANER_v2.2.md)** ✅ - 語意感知清洗、Equipment Precheck、SSOT 驅動
- **[BatchProcessor v1.3](docs/batch_processor/PRD_BATCH_PROCESSOR_v1.3.md)** - Manifest 生成、E406 驗證

### 機器學習與最佳化

- **[Feature Engineer v1.4](docs/feature_engineering/PRD_Feature_Engineer_v1.4.md)** ⭐ **(New!)**
  - **拓樸聚合特徵 (L2)** - Hop-N 傳播與邊界修正
  - **控制偏差特徵 (L3)** - Decay factor 與語意對齊
  - **GNN 資料匯出** - adjacency_matrix 與 node_types
  
- **[Model Training v1.4](docs/Model_Training/PRD_Model_Training_v1.4.md)** ⭐ **(New!)**
  - **GNN 訓練器** - Multi-Task 架構 (System + Component)
  - **Physics-Informed Loss** - E761-E762 物理守恆驗證
  - **Resource-Aware Training** - 記憶體預估與 OOM 預防
  
- **[Continual Learning v1.1](docs/Continual_Learning/PRD_Continual_Learning_v1.1.md)** ⭐ **(New!)**
  - **Layer-wise GEM** - 分層梯度投影 (防維度災難)
  - **Drift Detector** - PSI + KS + Cohen's d 綜合檢測
  - **RedisLock** - E815 分散式鎖 (TTL 死鎖預防)
  
- **[Optimization Engine v1.2](docs/Chiller_Plant_Optimization_Engine/PRD_Chiller_Plant_Optimization_V1.2.md)** - 黑盒優化、Fallback 機制、CL 整合

### Web 應用層 (Frontend & Backend Interface)

- **[Web 應用層架構與 API 介面規範 v1.1](docs/Web_Application_Layer/PRD_Web_Application_Architecture_V1.1.md)** - 系統架構邊界與前後端解耦
- **[Web API 介面規格設計 v1.1](docs/Web_Application_Layer/PRD_Web_API_Interface_V1.1.md)** - RESTful API 與 WebSocket 介面規範
- **[Web UI 前端頁面流程與狀態圖 v1.1](docs/Web_Application_Layer/PRD_UI_Flow_and_State_V1.1.md)** - 前端頁面結構與狀態轉換

---

## 🚧 實作路徑 (Implementation Roadmap)

### 當前狀態: Phase 0 Retrofit 準備中 → Sprint 3-5 開發

```
Sprint 1: Foundation ✅ 完成
├── ✅ Interface Contract v1.2 (PRD 已完成)
│   ├── E000-E999 錯誤代碼定義
│   ├── **新增: E750-E759 (GNN 拓樸), E800-E829 (CL), E840-E859 (OPT)**
│   ├── 7 個檢查點規格 + **#7 CL 整合**
│   └── Header Standardization 規則
│
├── ✅ System Integration v1.2 (已完成)
│   ├── PipelineContext (E000 時間基準)
│   ├── ETLConfig (Pydantic 模型)
│   ├── ConfigLoader (E406 同步檢查)
│   └── ETLContainer (4步驟初始化)
│
├── ✅ Feature Annotation v1.4 (PRD 已完成)
│   ├── Pydantic 模型 (ColumnAnnotation, EquipmentConstraint)
│   ├── **拓樸感知 (Topology Awareness)** - Graph 節點/邊緣
│   ├── **控制語意 (Control Semantics)** - Decay factor
│   ├── Excel 工具鏈 (Wizard、excel_to_yaml)
│   └── HVAC 設備限制條件
│
├── ✅ 程式碼審查優化 (已完成)
│   ├── Lazy Import 移除 (支援靜態分析)
│   └── STRICT_MODE 環境變數 (生產安全)
│
└── ✅ Sprint 1 Demo 展示 (已完成)
    ├── 系統架構圖 (Mermaid.js)
    ├── 錯誤代碼體系互動表格
    ├── Feature Annotation 依賴與前後比較
    └── 4步驟初始化流程與測試覆蓋率分析

Sprint 2: 核心 ETL ✅ 已完成 (4/4 完成)
├── ✅ Parser v2.1 (已完成，A級)
│   ├── 編碼自動偵測 (UTF-8/Big5/UTF-16)
│   ├── BOM 處理與移除
│   ├── 智慧標頭搜尋 (中文標頭支援)
│   ├── 時區強制轉換 (→ UTC/ns)
│   └── 輸出契約驗證 (E101-E105)
├── ✅ Parser v2.2 (已完成)
│   ├── Strategy Pattern 模組化架構
│   ├── GenericParser (V2.1 向後相容)
│   ├── SiemensSchedulerReportParser (CGMH-TY, Farglory O3, KMUH)
│   ├── 相容 shim + facade（舊入口維持可用）
│   └── 統一輸出契約（Cleaner V2.2 相容）
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
    │
    └── ✅ Interactive ETL Tester v1.5 (已完成)
        ├── Step 1→2 無縫整合
        ├── 欄位名稱一致性保證
        └── E409 Header Mismatch 預防

Phase 0: v1.4 Retrofit 🔧 待開始 (Sprint 3 前置，3.5-5 天)
├── ⏳ Phase 0.1: 錯誤代碼重分配 (IC-R01~R05)
│   ├── IC-R01: E750-E759 → GNN 拓樸錯誤
│   ├── IC-R02: E800-E808 → E840-E848 (OPT 遷移)
│   ├── IC-R03: 新增 E800-E829 (CL 錯誤)
│   ├── IC-R04: 更新既有代碼引用
│   └── IC-R05: ERROR_CODES 字典註冊
│
├── ⏳ Phase 0.2: 基礎設施補強 (FA-R01~R03)
│   ├── FA-R01: YAML SSOT 支援 topology 欄位
│   ├── FA-R02: Excel 範本 v1.4 欄位規則
│   └── FA-R03: excel_to_yaml.py 升級
│
└── ⏳ Phase 0.3: 核心 ETL 管線升級 (P-R01, C-R01, BP-R01)
    ├── P-R01: Parser 契約對齊 (topology/control_semantics 解析，避免 E103)
    ├── C-R01: Cleaner 邏輯增強 (對齊 E75x，放行 GNN 特徵，不誤殺)
    └── BP-R01: BatchProcessor 無損寫入 (節點/邊緣陣列型別不遺失)

Sprint 3: 特徵工程與模型訓練 ⏳ 待開始 (第 6-10 週，21-26 天)
├── ⏳ Feature Engineer v1.4
│   ├── FE-001~FE-007: 基礎特徵工程 (延續 v1.3)
│   ├── FE-008: 拓樸特徵生成與 Hop-N 修正 (E750-E759)
│   ├── FE-009: control_semantic 欄位輸出
│   └── FE-010: GNN 資料匯出 (adjacency_matrix, node_types, NaN 防護)
│       └── 輸出: topology_context → Model Training
│
├── ⏳ Model Training v1.4
│   ├── MT-001~MT-004: Resource-Aware 基礎設施
│   ├── MT-005: GNN Trainer (Captum GNNWrapper)
│   ├── MT-006: Physics-Informed Loss (E761-E762)
│   ├── MT-007: Multi-Task 架構 (System + Component)
│   ├── MT-009: Model Registry Index
│   └── MT-012: GNN 拓樸整合測試
│       └── 輸出: Model Registry → CL / Optimization
│
└── ⏳ Hybrid Consistency v1.0
    └── 系統級 vs 元件級預測一致性驗證

Sprint 4: 最佳化 + 持續學習 ⏳ 待開始 (第 10-13 週，12-15 天)
├── ⏳ Continual Learning v1.1 (並行開發)
│   ├── CL-001: UpdateOrchestrator (E800-E804)
│   ├── CL-002: DriftDetector (PSI + KS + Cohen's d)
│   ├── CL-003: GEMTrainer (Layer-wise 梯度投影)
│   ├── CL-004: EpisodicMemoryBuffer (Batch Mode Importance)
│   ├── CL-006: RedisLock (E815 TTL 死鎖預防)
│   └── CL-007: 設備異動處理 (E827-E828)
│       └── 輸出: 模型更新 → Optimization
│
├── ⏳ Equipment Validation v1.0
│   └── Cleaner-OPT 設備限制一致性驗證
│
└── ⏳ Optimization v1.2
    ├── OPT-001: Model Registry 載入 (E841/E842)
    ├── OPT-002: Feature Alignment 驗證 (E901-E904)
    ├── OPT-006: Fallback Handler (3層降級)
    └── OPT-008: CL 整合接口 (性能指標傳遞)

Sprint 5: 整合測試 ⏳ 待開始 (第 13-15 週，10-12 天)
├── ⏳ Wizard Technical Blockade v1.0
│   └── Import Guard + 檔案系統保護 + CI/CD Hook
│
└── ⏳ 端到端整合測試
    ├── INT-001: Parser→Cleaner→BP→FE 流程
    ├── INT-002: FE→Training→OPT 流程
    ├── INT-002a: Training→CL→Model Update 流程 (檢查點 #7a)
    ├── INT-005a: GNN 拓樸傳遞測試 (E750-E759)
    ├── INT-006a: CL 持續學習迴路測試 (E800-E829)
    └── INT-009: 併發更新測試 (E815 分散式鎖)
```

### 關鍵里程碑

| 里程碑 | 時間 | 狀態 |
|:---|:---:|:---:|
| M1: 基礎就緒 | 第 2 週末 | ✅ 完成 |
| M2: ETL 就緒 | 第 5 週末 | ✅ 完成 |
| M2.1: Parser v2.2 重構 | 第 6 週末 | ✅ 完成 |
| **M2.5: Phase 0 Retrofit** | **第 7 週初** | ⏳ **待開始** |
| **M3: ML 就緒** | **第 10 週末** | ⏳ 待開始 |
| **M4: 最佳化 + CL 就緒** | **第 13 週末** | ⏳ 待開始 |
| **M5: 系統上線** | **第 17 週末** | ⏳ 待開始 |

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
| CI/CD 品質門禁 | 全部 140 項測試通過 | ✅ **通過** |

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
- **[Sprint 2 執行摘要](docs/專案任務排程/Sprint_2_執行摘要.md)** - Parser v2.1 + v2.2、Cleaner v2.2 詳細說明
- **[Sprint 2 審查報告](docs/專案任務排程/Sprint_2_Review_Report.md)** - 審查詳情與下游預警

確保所有新代碼遵守：
1. **Foundation First Policy** - 按照 Sprint 順序實施
2. **錯誤代碼規範** - 使用 E000-E999 錯誤代碼體系
3. **Temporal Baseline** - 禁止使用 `datetime.now()`，必須使用 PipelineContext
4. **職責分離** - Cleaner 不傳遞 `device_role`，Feature Engineer 直接查詢 Annotation
5. **唯讀防護** - 禁止直接修改 YAML，必須透過 Excel → excel_to_yaml.py 流程

---

## 🎯 PRD 已完成項目 (Sprint 3-4 規劃完成)

> ⚠️ **注意**: 以下項目為 **PRD (產品需求文件) 已完成**，實際程式碼開發將在 Sprint 3-4 進行

### ✅ 3.1 Feature Annotation v1.4 (拓樸感知與控制語意) - PRD 完成

**PRD 完成日期**: 2026-02-26  
**程式碼開發**: ⏳ Sprint 3 待開發

**核心擴充**:

| 新增欄位 | 說明 | 應用 |
|:---|:---|:---|
| `upstream_equipment_id` | 上游設備 ID，建立有向圖邊界 | GNN 輸入、拓樸聚合特徵 |
| `point_class` | 點位型態 (Sensor/Setpoint/Command/Alarm/Status) | 控制偏差計算 |
| `control_domain` | 控制域 (chilled_water/condenser_water/air_handling) | 控制語意分組 |
| `setpoint_pair_id` | 對應 Setpoint ID | 自動 Sensor-Setpoint 配對 |

**錯誤代碼實作**: E410-E429 (拓樸錯誤), E430-E449 (控制語意錯誤)

**文件**: [PRD_Feature_Annotation_Specification_V1.4.md](./docs/Feature%20Annotation%20Specification/PRD_Feature_Annotation_Specification_V1.4.md)

---

### ✅ 3.2 Feature Engineer v1.4 (拓樸聚合與控制偏差) - PRD 完成

**PRD 完成日期**: 2026-02-26  
**程式碼開發**: ⏳ Sprint 3 待開發 (FE-008~FE-010)

**分層特徵生成**:

```
L0: 原始特徵 (Raw Sensor Data)
L1: 統計特徵 (Lag, Rolling, Diff) - v1.3 既有
L2: 🆕 拓樸特徵 (上游設備聚合) - e.g., chiller_01_upstream_ct_temp_mean
L3: 🆕 控制偏差特徵 (ΔT = Sensor - Setpoint) - e.g., chiller_01_chwst_deviation
```

**輸出擴充**:
- `topology_context`: 設備連接圖 + Adjacency Matrix (供 GNN 使用)
- `control_semantics_context`: 控制對配對資訊
- `Feature Manifest v2.1`: 包含拓樸與控制語意規格

**錯誤代碼實作**: E413 (Topology 版本不符), E601-E604

**下游契約**: Model Training v1.4+ (支援 GNN 訓練)

**文件**: [PRD_FEATURE_ENGINEER_V1.4.md](./docs/feature_engineering/PRD_FEATURE_ENGINEER_V1.4.md)

---

### ✅ 3.3 Model Training v1.4 (GNN 與物理守恆損失) - PRD 完成

**PRD 完成日期**: 2026-02-26  
**程式碼開發**: ⏳ Sprint 3 待開發 (MT-005~MT-007, MT-012)

**新增訓練器**:

| 訓練器 | 用途 | 特色 |
|:---|:---|:---|
| `GNNTrainer` | 圖神經網路訓練 | 使用 PyTorch Geometric，學習設備間熱力傳遞 |
| `PhysicsInformedHybridLoss` | 物理守恆約束 | 強制 System-Level ≈ Component-Level 總和 |

**訓練模式**:
- A: single_target (單一目標)
- B: multi_target (多目標批次)
- C: hybrid (傳統 Hybrid)
- D: 🆕 gnn_only (GNN-Only)
- E: 🆕 gnn_ensemble (GNN + XGBoost + LightGBM)

**錯誤代碼實作**: E750-E759 (GNN 專用錯誤)

**文件**: [PRD_Model_Training_v1.4.md](./docs/Model_Training/PRD_Model_Training_v1.4.md)

---

### ✅ 3.4 Continual Learning v1.1 (GEM 與概念漂移) - PRD 完成

**PRD 完成日期**: 2026-02-26 (升級至 v1.1 含 Layer-wise GEM)  
**程式碼開發**: ⏳ Sprint 4 待開發 (CL-001~CL-008)

**核心模組**:

| 模組 | 功能 |
|:---|:---|
| `UpdateOrchestrator` | 更新編排器，協調觸發→訓練→驗證→部署 |
| `GEMTrainer` | 梯度情境記憶訓練，防止災難性遺忘 |
| `DriftDetector` | 概念漂移檢測 (性能/統計/分布漂移) |
| `EpisodicMemoryBuffer` | 情境記憶緩衝，儲存代表性歷史樣本 |

**更新觸發條件**:
- E800: MAPE 劣化 > 15%
- E801: 絕對 MAPE > 8%
- E802: 定期更新 (30天)
- E803: 概念漂移檢測
- E804: 設備異動通知

**錯誤代碼實作**: E800-E829 (持續學習專用)

**文件**: [PRD_Continual_Learning_v1.1.md](./docs/Continual_Learning/PRD_Continual_Learning_v1.1.md)

---

### ✅ 3.5 Interface Contract v1.2 (v1.4 相容性) - PRD 完成

**PRD 完成日期**: 2026-02-26  
**程式碼實作**: ⏳ Phase 0 Retrofit 待完成 (IC-R01~R05)

**錯誤代碼分層擴充**:

| 範圍 | 用途 | 狀態 |
|:---:|:---|:---:|
| E410-E429 | 🆕 Topology Awareness | 新增 |
| E430-E449 | 🆕 Control Semantics | 新增 |
| E750-E759 | 🆕 GNN Training | 新增 |
| E760-E799 | 🔄 Hybrid Consistency | 遷移自 E750-E799 |
| E800-E829 | 🆕 Continual Learning | 新增 |
| E830-E899 | 🔄 Optimization | 遷移自 E800-E899 |

**版本相容性矩陣**: 新增 v1.4 推薦配置與升級路徑

**文件**: [PRD_Interface_Contract_v1.2.md](./docs/Interface%20Contract/PRD_Interface_Contract_v1.2.md)

---

## 📖 延伸閱讀

- [專案任務排程](docs/專案任務排程/專案任務排程文件.md) - 系統架構、風險評估、實施建議
- [Sprint 1 執行摘要](docs/專案任務排程/Sprint_1_執行摘要.md) - 詳細的完成項目與測試報告
- [Sprint 1 審查報告](docs/專案任務排程/Sprint_1_Review_Report.md) - 審查結論與優化項目
- [Sprint 2 執行摘要](docs/專案任務排程/Sprint_2_執行摘要.md) - Parser v2.1 + v2.2、Cleaner v2.2 詳細摘要
- [Sprint 2 審查報告](docs/專案任務排程/Sprint_2_Review_Report.md) - 審查結論與下游預警
- [Feature Annotation 實作摘要](docs/Feature%20Annotation%20Specification/IMPLEMENTATION_SUMMARY.md) - Feature Annotation v1.3 詳細實作說明
- **🆕 [Feature Annotation v1.4](docs/Feature%20Annotation%20Specification/PRD_Feature_Annotation_Specification_V1.4.md)** - 拓樸感知與控制語意規範
- **🆕 [Feature Engineer v1.4](docs/feature_engineering/PRD_FEATURE_ENGINEER_V1.4.md)** - 拓樸聚合與控制偏差特徵
- **🆕 [Model Training v1.4](docs/Model_Training/PRD_Model_Training_v1.4.md)** - GNN 訓練器與物理守恆損失
- **🆕 [Continual Learning v1.1](docs/Continual_Learning/PRD_Continual_Learning_v1.1.md)** - GEM 演算法與概念漂移檢測
- **🆕 [Interface Contract v1.2](docs/Interface%20Contract/PRD_Interface_Contract_v1.2.md)** - v1.4 相容性與錯誤代碼分層

---

**最後更新**: 2026-02-26  
**架構版本**: v2.1-執行版  
**文件狀態**: 🟢 Sprint 1-2 完成｜Phase 0 Retrofit 就緒｜Sprint 3-5 任務確立
