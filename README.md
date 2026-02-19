# HVAC Analytics - Core Engine (v1.3 Architecture)

**核心引擎狀態**: 🚧 **Sprint 1 進行中 (2/3 完成)**  
**最後更新**: 2026-02-19

---

## 📊 專案進度總覽

| Sprint | 任務 | 狀態 | 測試 |
|:---:|:---|:---:|:---:|
| 1 | 1.1 Interface Contract v1.1 | ✅ 已完成 | 已驗證 |
| 1 | 1.2 System Integration v1.2 | ✅ 已完成 | 35/35 通過 |
| 1 | 1.3 Feature Annotation v1.2 | ⏳ 進行中 | - |
| 2 | 2.1 Parser v2.1 | ⏳ 待開始 | - |
| 2 | 2.2 Cleaner v2.2 | ⏳ 待開始 | - |
| 2 | 2.3 BatchProcessor v1.3 | ⏳ 待開始 | - |

[📋 查看完整任務排程](./docs/專案任務排程/專案任務排程文件.md) | [📈 Sprint 1 執行摘要](./docs/專案任務排程/Sprint_1_執行摘要.md)

---

## 🔍 專案概覽

HVAC 冰水系統資料處理與分析的核心引擎，專注於提供高可信度 (High-Fidelity) 的 ETL 管道與物理感知 (Physics-Aware) 的能耗優化模型。本專案核心目標是建立後端工程師可輕鬆整合的黑盒子模組，並確保設備邏輯一致性與時間基準準確性。

### 設計原則

- **契約導向設計 (Contract-First)**: 嚴格定義模組間介面與檢查點
- **單一真相源 (SSOT)**: 所有配置與常數集中管理
- **Foundation First**: 基礎設施優先，確保下游模組有穩固依賴
- **Fail Fast**: 寧可終止流程，也不傳遞可疑資料

---

## 📁 專案結構 (Target Architecture v1.3)

```
HVAC_Analytics/
├── src/                        # 核心源碼
│   ├── container.py            # ✅ ETLContainer (4步驟初始化)
│   ├── context.py              # ✅ PipelineContext (時間基準)
│   ├── interface.py            # ★ Facade - 後端整合入口
│   ├── schemas.py              # Pydantic I/O 定義
│   ├── etl/                    # ETL 管道
│   │   ├── parser.py           # v2.1 報表解析 (E1xx Error Codes)
│   │   ├── cleaner.py          # v2.2 資料清洗 + Equipment Precheck (E2xx)
│   │   ├── batch_processor.py  # v1.3 批次處理 + Manifest (E3xx)
│   │   ├── feature_engineer.py # v1.3 特徵工程 + Device Role Aware (E6xx)
│   │   └── config_models.py    # ✅ SSOT 配置模型 (E000-E999)
│   ├── utils/                  
│   │   └── config_loader.py    # ✅ ConfigLoader (E406, 檔案鎖)
│   ├── modeling/               # [TODO] 機器學習模型
│   ├── optimization/           # 優化演算法
│   └── features/               # [TODO] 特徵管理
├── config/                     # 配置檔案
├── tools/                      # 工具鏈
├── tests/                      # 單元測試
│   └── test_container_initialization.py  # ✅ 35 項測試
├── docs/                       # 專案文檔
│   ├── 專案任務排程/           # 任務排程與執行摘要
│   ├── Interface Contract/     # Interface Contract v1.1
│   └── System Integration/     # System Integration v1.2
└── main.py                     # CLI 主程式
```

---

## 🎯 已完成項目 (Sprint 1 - 2/3)

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
```

### 使用 Facade (推薦)

```python
from src.interface import HVACService
from src.schemas import OptimizationContext

# 初始化服務（將自動啟動 ETLContainer）
service = HVACService(site_id="cgmh_ty")

# 執行最佳化
context = OptimizationContext(
    load_rt=500.0,
    temp_db_out=30.0,
    timestamp="2024-06-01T12:00:00Z"
)
result = service.optimize(context)
```

### CLI 執行

```bash
# 執行完整 Pipeline（將遵循 v1.2 初始化順序）
python main.py pipeline data/raw/report.csv --site cgmh_ty
```

---

## 🧪 測試

### 執行測試

```bash
# 執行 System Integration 測試
python3 -m pytest tests/test_container_initialization.py -v

# 預期結果: 35 passed
```

### 測試覆蓋

| 類別 | 測試數 | 說明 |
|:---|:---:|:---|
| PipelineContext | 9 | 單例、E000、時間漂移、執行緒安全 |
| ETLConfig | 6 | Pydantic、E405、版本相容性 |
| ConfigLoader | 7 | E406、E007、檔案鎖 |
| ETLContainer | 7 | 4 步驟初始化順序 |
| 時間基準傳遞 | 6 | 跨日、注入、驗證 |
| **總計** | **35** | **全部通過** |

---

## 📚 專案文檔

### 核心架構規範

- **[Interface Contract v1.1](docs/Interface%20Contract/PRD_Interface_Contract_v1.1.md)** ⭐ 
  - 10 個檢查點定義 (E000 時間基準 → E901 特徵對齊)
  - 100+ 錯誤代碼體系 (E000-E999)
  - Temporal Baseline 時間基準規範

- **[System Integration v1.2](docs/System%20Integration/PRD_System_Integration_v1.2.md)** ⭐ **(New!)**
  - 系統整合架構與 4 步驟初始化順序
  - Foundation First Policy
  - Container 依賴注入機制

### 任務排程與執行摘要

- **[專案任務排程](docs/專案任務排程/專案任務排程文件.md)** - 完整 Sprint 規劃
- **[Sprint 1 執行摘要](docs/專案任務排程/Sprint_1_執行摘要.md)** - Interface Contract & System Integration 詳細摘要

### ETL 管道模組

- **[Parser v2.1](docs/parser/PRD_Parser_V2.1.md)** - Header Standardization、UTC/ns 時間戳
- **[Cleaner v2.2](docs/cleaner/PRD_CLEANER_v2.2.md)** - 語意感知清洗、Equipment Precheck
- **[BatchProcessor v1.3](docs/batch_processor/PRD_BATCH_PROCESSOR_v1.3.md)** - Manifest 生成、E406 驗證

### 機器學習與最佳化

- **[Model Training v1.3](docs/Model_Training/PRD_Model_Training_v1.3.md)** - 三種訓練模式、Resource-Aware Training
- **[Optimization Engine v1.2](docs/Chiller_Plant_Optimization_Engine/PRD_Chiller_Plant_Optimization_V1.2.md)** - 黑盒優化、Fallback 機制

---

## 🚧 實作路徑 (Implementation Roadmap)

### 當前狀態: Sprint 1 進行中 (2/3 完成)

```
Sprint 1: Foundation
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
└── ⏳ Feature Annotation v1.2 (進行中)
    ├── Excel 範本設計
    ├── YAML Schema
    ├── excel_to_yaml 轉換器
    └── FeatureAnnotationManager

Sprint 2: 核心 ETL (待開始)
├── Parser v2.1
├── Cleaner v2.2
└── BatchProcessor v1.3
```

### 下一步

1. 完成 1.3 Feature Annotation v1.2
2. 啟動 Sprint 2: 核心 ETL（Parser、Cleaner、BatchProcessor 升級）

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

---

## 📖 延伸閱讀

- [專案任務排程](docs/專案任務排程/專案任務排程文件.md) - 系統架構、風險評估、實施建議
- [Sprint 1 執行摘要](docs/專案任務排程/Sprint_1_執行摘要.md) - 詳細的完成項目與測試報告

---

**最後更新**: 2026-02-19  
**架構版本**: v1.3  
**文件狀態**: 🚧 Sprint 1 進行中 (2/3 完成)
