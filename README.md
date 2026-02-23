# HVAC Analytics - Core Engine (v1.3 Architecture)

**核心引擎狀態**: 🚧 **Sprint 2 進行中 (1/3 完成)**  
**最後更新**: 2026-02-23

---

## 📊 專案進度總覽

| Sprint | 任務 | 狀態 | 測試/展示 |
|:---:|:---|:---:|:---:|
| 1 | 1.1 Interface Contract v1.1 | ✅ 已完成 | 已驗證 |
| 1 | 1.2 System Integration v1.2 | ✅ 已完成 | 35/35 通過 |
| 1 | 1.3 Feature Annotation v1.3 | ✅ 已完成 | 18/18 通過 |
| 1 | 1.4 程式碼審查優化 | ✅ 已完成 | 72/72 通過 |
| 1 | **1.5 Sprint 1 Demo 展示** | ✅ **已完成** | **[🎨 查看 Demo](tools/demo/index.html)** |
| 2 | 2.1 Parser v2.1 | ✅ **已完成** | 8 案例 |
| 2 | 2.2 Cleaner v2.2 | 🚧 **準備中** | - |
| 2 | 2.3 BatchProcessor v1.3 | ⏳ **待開始** | - |

**Sprint 1 總計**: 72 項測試全部通過 ✅  
**Sprint 2 進度**: 1/3 完成 (Parser v2.1 ✅)

[📋 查看完整任務排程](./docs/專案任務排程/專案任務排程文件.md) | [📈 Sprint 1 執行摘要](./docs/專案任務排程/Sprint_1_執行摘要.md) | [📈 Sprint 2 執行摘要](./docs/專案任務排程/Sprint_2_執行摘要.md)

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
│   │   ├── cleaner.py          # v2.2 資料清洗 + Equipment Precheck (E2xx)
│   │   ├── batch_processor.py  # v1.3 批次處理 + Manifest (E3xx)
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

# 執行全部測試
python3 -m pytest tests/ -v

# 預期結果: 80+ passed (Sprint 1: 72 + Parser: 8)
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
| Parser v2.1 | 8 | 編碼、時區、標頭、契約驗證 |
| 其他測試 | 19 | ETL 整合、能源模型 |
| **總計** | **80** | **Sprint 1: 72 + Sprint 2: 8** |

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
- **[Sprint 2 執行摘要](docs/專案任務排程/Sprint_2_執行摘要.md)** - Parser v2.1 完成摘要、Cleaner/BatchProcessor 規劃

### ETL 管道模組

- **[Parser v2.1](docs/parser/PRD_Parser_V2.1.md)** ✅ - Header Standardization、UTC/ns 時間戳、編碼自動偵測
- **[Cleaner v2.2](docs/cleaner/PRD_CLEANER_v2.2.md)** - 語意感知清洗、Equipment Precheck
- **[BatchProcessor v1.3](docs/batch_processor/PRD_BATCH_PROCESSOR_v1.3.md)** - Manifest 生成、E406 驗證

### 機器學習與最佳化

- **[Model Training v1.3](docs/Model_Training/PRD_Model_Training_v1.3.md)** - 三種訓練模式、Resource-Aware Training
- **[Optimization Engine v1.2](docs/Chiller_Plant_Optimization_Engine/PRD_Chiller_Plant_Optimization_V1.2.md)** - 黑盒優化、Fallback 機制

---

## 🚧 實作路徑 (Implementation Roadmap)

### 當前狀態: Sprint 1 完成 (4/4，含 Demo)

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

Sprint 2: 核心 ETL 🚧 進行中 (1/3 完成)
├── ✅ Parser v2.1 (已完成)
│   ├── 編碼自動偵測 (UTF-8/Big5/UTF-16)
│   ├── BOM 處理與移除
│   ├── 智慧標頭搜尋 (中文標頭支援)
│   ├── 時區強制轉換 (→ UTC/ns)
│   └── 輸出契約驗證 (E101-E105)
├── 🚧 Cleaner v2.2 (準備中)
│   └── E350 設備邏輯、語意感知清洗
└── ⏳ BatchProcessor v1.3 (待開始)
    └── Manifest、E408 檢查
```

### 下一步

1. 啟動 **Sprint 2: 核心 ETL**（Parser、Cleaner、BatchProcessor 升級）
2. FeatureAnnotationManager 整合至 Cleaner v2.2（device_role 查詢、E350 設備邏輯預檢）

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
- [Feature Annotation 實作摘要](docs/Feature%20Annotation%20Specification/IMPLEMENTATION_SUMMARY.md) - Feature Annotation v1.3 詳細實作說明

---

**最後更新**: 2026-02-23  
**架構版本**: v1.3  
**文件狀態**: ✅ Sprint 1 完成 (4/4，含 Demo)
