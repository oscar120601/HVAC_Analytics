# HVAC Analytics - Core Engine (v1.3 Architecture)

**核心引擎狀態**: 🏗️ **架構完善階段 (Architecture Refinement)**  
我們已完成從 v1.0 到 v1.3 的架構升級,文件庫 (`docs/`) 已全面更新至最新規範,包含 Interface Contract v1.1、Feature Annotation v1.3、以及所有核心模組的 v1.3 版本。此外，所有 PRD 文件皆已生成 HTML 格式以便於閱讀。核心程式碼 (`src/`) 正在按照 Foundation First Policy 逐步實施。

## 🔍 專案概覽

HVAC 冰水系統資料處理與分析的核心引擎,專注於提供高可信度 (High-Fidelity) 的 ETL 管道與物理感知 (Physics-Aware) 的能耗優化模型。本專案核心目標是建立後端工程師可輕鬆整合的黑盒子模組,並確保設備邏輯一致性與時間基準準確性。

## 📁 專案結構 (Target Architecture v1.3)

```
HVAC_Analytics/
├── src/                        # 核心源碼
│   ├── container.py            # [TODO] DI Container (系統心臟)
│   ├── context.py              # [TODO] Pipeline Context (時間基準)
│   ├── interface.py            # ★ Facade - 後端整合入口
│   ├── schemas.py              # Pydantic I/O 定義
│   ├── core/                   # [TODO] 核心基礎設施
│   │   └── temporal_baseline.py # Temporal Baseline 時間基準
│   ├── features/               # [TODO] 特徵管理
│   │   └── annotation_manager.py # v1.3 Excel-to-YAML SSOT & Constraints
│   ├── equipment/              # [TODO] 設備驗證
│   │   └── equipment_validator.py # v1.0 設備依賴關係驗證
│   ├── etl/                    # ETL 管道
│   │   ├── parser.py           # v2.1 報表解析 (E1xx Error Codes)
│   │   ├── cleaner.py          # v2.2 資料清洗 + Equipment Precheck (E2xx)
│   │   ├── batch_processor.py  # v1.3 批次處理 + Manifest (E3xx)
│   │   ├── feature_engineer.py # v1.3 特徵工程 + Device Role Aware (E6xx)
│   │   └── config_models.py    # SSOT 配置模型
│   ├── modeling/               # 機器學習模型
│   │   ├── training_pipeline.py # v1.3 Resource-Aware Training
│   │   ├── model_registry.py   # 模型註冊與版本管理
│   │   └── validation/         # 模型驗證
│   │       └── hybrid_consistency.py # v1.0 Hybrid 一致性檢查
│   ├── optimization/           # 優化演算法
│   │   ├── engine.py           # v1.2 Optimization Engine
│   │   ├── constraints.py      # 設備限制條件
│   │   ├── scenarios.py        # 情境模擬
│   │   └── fallback.py         # Fallback 機制
│   └── utils/                  
│       └── config_loader.py    # [TODO] 統一配置載入
├── config/                     # 配置檔案
│   ├── settings.yaml           # 系統參數
│   └── features/               # [TODO] 案場特徵定義 (YAML SSOT)
│       ├── base.yaml           # 基礎特徵定義
│       └── sites/              # 各案場特徵 (繼承 base)
├── tools/                      # 工具鏈
│   ├── features/               # 特徵標註工具
│   │   ├── excel_to_yaml.py    # Excel 轉 YAML 轉換器
│   │   └── wizard.py           # 特徵標註 Wizard
│   └── docs/                   # 文件工具
│       └── md_to_html.py       # Markdown 轉 HTML 工具
├── docs/                       # 專案文檔 (全面更新至 v1.3，含 HTML 版本)
│   ├── Interface Contract/     # ★ Interface Contract v1.1
│   ├── Feature Annotation Specification/ # Feature Annotation v1.3 (New!)
│   ├── System Integration/     # System Integration v1.2
│   ├── Chiller_Plant_Optimization_Engine/ # Optimization v1.2
│   ├── Model_Training/         # Model Training v1.3
│   ├── Equipment_Dependency_Validation/ # Equipment Validation v1.0
│   ├── Hybrid_Model_Consistency/ # Hybrid Consistency v1.0
│   ├── parser/                 # Parser v2.1
│   ├── cleaner/                # Cleaner v2.2
│   ├── batch_processor/        # BatchProcessor v1.3
│   ├── feature_engineering/    # Feature Engineer v1.3
│   └── system_overview/        # 系統總覽與分析報告
├── tests/                      # 單元測試
├── main.py                     # CLI 主程式
└── requirements.txt            # Python 依賴
```

## 📚 專案文檔 (已更新 2026-02-14)

所有 PRD 皆已升級以支援 **Interface Contract v1.1** 定義的 **10 個檢查點**、**E000-E999 錯誤代碼體系**、**Temporal Baseline 時間基準機制**,以及 **Equipment Validation 設備邏輯同步**。

**🔥 重大更新**: 新增 HTML 格式文件，方便離線閱讀與審閱。

### 🎯 核心架構規範

- **[Interface Contract v1.1](docs/Interface%20Contract/PRD_Interface_Contract_v1.1.md)** ([HTML](docs/Interface%20Contract/PRD_Interface_Contract_v1.1.html)) ⭐ 
  - 10 個檢查點定義 (E000 時間基準 → E901 特徵對齊)
  - 100+ 錯誤代碼體系 (E000-E999)
  - Temporal Baseline 時間基準規範
  - Feature Alignment 特徵對齊機制

- **[Feature Annotation Specification v1.3](docs/Feature%20Annotation%20Specification/PRD_Feature_Annotation_Specification_V1.3.md)** ([HTML](docs/Feature%20Annotation%20Specification/PRD_Feature_Annotation_Specification_V1.3.html)) ⭐ **(New!)**
  - Excel → YAML SSOT 單向流程 (Import Guard 防護)
  - HVAC 專用設備分類與命名規範 (Taxonomy)
  - Equipment Constraints (E350-E357) 定義於 YAML SSOT
  - Header Standardization 正規化規則整合

- **[System Integration v1.2](docs/System%20Integration/PRD_System_Integration_v1.2.md)** ([HTML](docs/System%20Integration/PRD_System_Integration_v1.2.html))
  - 系統整合架構與初始化順序
  - Foundation First Policy
  - Container 依賴注入機制

### 🔧 ETL 管道模組

- **[Parser v2.1](docs/parser/PRD_Parser_V2.1.md)** ([HTML](docs/parser/PRD_Parser_V2.1.html))
  - Header Standardization (snake_case)
  - 強制 UTC/ns 時間戳輸出
  - E1xx 錯誤處理

- **[Cleaner v2.2](docs/cleaner/PRD_CLEANER_v2.2.md)** ([HTML](docs/cleaner/PRD_CLEANER_v2.2.html))
  - 語意感知清洗 (device_role 調整閾值)
  - Equipment Validation Precheck (E350)
  - 職責分離三層防護 (白名單 + Schema 淨化 + CI Gate)
  - E2xx 錯誤處理

- **[BatchProcessor v1.3](docs/batch_processor/PRD_BATCH_PROCESSOR_v1.3.md)** ([HTML](docs/batch_processor/PRD_BATCH_PROCESSOR_v1.3.html))
  - Manifest 生成 (annotation_audit_trail + equipment_validation_audit)
  - Temporal Baseline 傳遞
  - E406 同步驗證與文件鎖
  - E3xx 錯誤處理

- **[Feature Engineer v1.3](docs/feature_engineering/PRD_FEATURE_ENGINEER_V1.3.md)** ([HTML](docs/feature_engineering/PRD_FEATURE_ENGINEER_V1.3.html))
  - Metadata 分層消費 (Manifest 物理屬性 + Annotation device_role)
  - Group Policy 語意感知 (backup 設備調整窗口)
  - Data Leakage 防護 (shift(1) + cutoff_timestamp)
  - E6xx 錯誤處理

### 🤖 機器學習與優化

- **[Model Training v1.3](docs/Model_Training/PRD_Model_Training_v1.3.md)** ([HTML](docs/Model_Training/PRD_Model_Training_v1.3.html))
  - 三種訓練模式 (System-Level, Component-Level, Hybrid)
  - Resource-Aware Training (Kubernetes/Docker 資源管理)
  - 自動化模型註冊 (model_registry_index.json)
  - Feature Alignment 驗證 (E901-E904)
  - E7xx 錯誤處理

- **[Chiller Plant Optimization Engine v1.2](docs/Chiller_Plant_Optimization_Engine/PRD_Chiller_Plant_Optimization_V1.2.md)** ([HTML](docs/Chiller_Plant_Optimization_Engine/PRD_Chiller_Plant_Optimization_V1.2.html))
  - 黑盒優化 (Optuna + XGBoost 預測)
  - Equipment Validation 整合
  - Feature Vectorization (E901-E904 對齊)
  - 多目標優化 (COP + 舒適度)
  - Fallback 機制

- **[Hybrid Model Consistency v1.0](docs/Hybrid_Model_Consistency/PRD_Hybrid_Model_Consistency_v1.0.md)** ([HTML](docs/Hybrid_Model_Consistency/PRD_Hybrid_Model_Consistency_v1.0.html))
  - System-Level vs Component-Level 一致性檢查
  - 差異 >5% 警告, >15% 錯誤
  - E75x 錯誤處理

### 🔍 設備驗證與特殊模組

- **[Equipment Dependency Validation v1.0](docs/Equipment_Dependency_Validation/PRD_Equipment_Dependency_Validation_v1.0.md)** ([HTML](docs/Equipment_Dependency_Validation/PRD_Equipment_Dependency_Validation_v1.0.html))
  - ETL 階段物理邏輯一致性檢查
  - 設備依賴關係驗證
  - 歷史資料驗證

- **[Wizard Technical Blockade v1.0](docs/Wizard_Technical_Blockade/PRD_Wizard_Technical_Blockade_V1.0.md)** ([HTML](docs/Wizard_Technical_Blockade/PRD_Wizard_Technical_Blockade_V1.0.html))
  - Feature Annotation Wizard 技術封鎖機制
  - 防止並發修改與資料競態

### 📊 分析報告

- **[PRD 全面分析報告](docs/system_overview/PRD_Analysis_Report.md)** ([HTML](docs/system_overview/PRD_Analysis_Report.html)) 🆕
  - 系統架構總覽與依賴圖
  - 10+ 核心模組詳細分析
  - 關鍵風險評估 (Dependency Deadlock, Physics Logic Decoupling, Temporal Inconsistency)
  - 實施優先級矩陣
  - 測試策略建議

## 🚀 整合指南 (Usage)

### 方式 1: 使用 Facade (推薦)

```python
from src.interface import HVACService
from src.schemas import OptimizationContext

# 初始化服務 (將自動啟動 ETLContainer)
service = HVACService(site_id="cgmh_ty")

# 執行最佳化
context = OptimizationContext(
    load_rt=500.0,
    temp_db_out=30.0,
    timestamp="2024-06-01T12:00:00Z"
)
result = service.optimize(context)
```

### 方式 2: CLI 執行

```bash
# 執行完整 Pipeline (將遵循 v1.2 初始化順序)
python main.py pipeline data/raw/report.csv --site cgmh_ty
```

## 🚧 實作路徑 (Implementation Roadmap)

目前專案處於 **Phase 1: Foundation** 階段,遵循 **Foundation First Policy**:

### Sprint 1: Foundation (0% - 待實施)
- [ ] **Interface Contract v1.1** (錯誤代碼定義)
  - [ ] `src/exceptions.py` - 錯誤代碼常數與異常類別
  - [ ] 檢查點規範文件
- [ ] **Temporal Baseline** (時間基準機制)
  - [ ] `src/core/temporal_baseline.py` - PipelineContext
  - [ ] E000 檢查機制
- [ ] **Feature Annotation v1.3** (YAML SSOT & HVAC Constraints)
  - [ ] `src/features/annotation_manager.py` - FeatureAnnotationManager
  - [ ] `tools/features/excel_to_yaml.py` - Excel → YAML 轉換工具
  - [ ] `tools/features/wizard.py` - Wizard 自動備份與預覽
  - [ ] E406 同步檢查與 Header Standardization
- [ ] **Equipment Validation SSOT**
  - [ ] `src/etl/config_models.py` - EQUIPMENT_VALIDATION_CONSTRAINTS
  - [ ] 基礎驗證邏輯

### Sprint 2: Integration (0% - 待實施)
- [ ] **Parser v2.1**
  - [ ] Header Standardization
  - [ ] UTC/ns 時間戳轉換
  - [ ] E1xx 錯誤處理
- [ ] **Cleaner v2.2**
  - [ ] 語意感知清洗
  - [ ] Equipment Validation Precheck
  - [ ] 職責分離三層防護
  - [ ] E2xx 錯誤處理
- [ ] **BatchProcessor v1.3**
  - [ ] Manifest 生成
  - [ ] E406 同步驗證
  - [ ] Parquet 輸出驗證
  - [ ] E3xx 錯誤處理
- [ ] **Feature Engineer v1.3**
  - [ ] Metadata 分層消費
  - [ ] Group Policy 語意感知
  - [ ] Data Leakage 防護
  - [ ] E6xx 錯誤處理

### Sprint 3: ML & Optimization (0% - 待實施)
- [ ] **Model Training v1.3**
  - [ ] ResourceManager (記憶體監控與檢查點)
  - [ ] 三種訓練模式
  - [ ] Feature Alignment 驗證
  - [ ] E7xx 錯誤處理
- [ ] **Optimization Engine v1.2**
  - [ ] 黑盒優化
  - [ ] Equipment Validation 整合
  - [ ] Feature Vectorization
  - [ ] E9xx 錯誤處理
- [ ] **Hybrid Consistency v1.0**
  - [ ] 一致性檢查
  - [ ] 診斷報告生成
  - [ ] E75x 錯誤處理

### 文檔完成度
- [x] **PRD 文檔更新** (100%)
  - [x] Interface Contract v1.1
  - [x] Feature Annotation v1.2
  - [x] 所有核心模組升級至 v1.3
  - [x] PRD 全面分析報告
  - [x] **HTML 文檔生成** (New!)

## 🤝 貢獻

請務必先閱讀以下核心文檔:
- **[Interface Contract v1.1](docs/Interface%20Contract/PRD_Interface_Contract_v1.1.md)** - 錯誤代碼規範與檢查點定義
- **[Feature Annotation v1.3](docs/Feature%20Annotation%20Specification/PRD_Feature_Annotation_Specification_V1.3.md)** - YAML SSOT 機制與 HVAC 命名規範
- **[PRD 分析報告](docs/system_overview/PRD_Analysis_Report.md)** - 系統架構與實施建議

確保所有新代碼遵守:
1. **Foundation First Policy** - 按照 Sprint 1 → Sprint 2 → Sprint 3 順序實施
2. **錯誤代碼規範** - 使用 E000-E999 錯誤代碼體系
3. **Temporal Baseline** - 禁止使用 `datetime.now()`,必須使用 `pipeline_origin_timestamp`
4. **職責分離** - Cleaner 不傳遞 `device_role`,Feature Engineer 直接查詢 Annotation

## 📖 延伸閱讀

- [PRD 全面分析報告](docs/system_overview/PRD_Analysis_Report.md) - 系統架構、風險評估、實施建議
- [Foundation First Policy](docs/Interface%20Contract/PRD_Interface_Contract_v1.1.md#foundation-first-policy) - 實施順序與依賴管理
- [錯誤代碼體系](docs/Interface%20Contract/PRD_Interface_Contract_v1.1.md#error-codes) - E000-E999 完整定義

---

**最後更新**: 2026-02-14  
**架構版本**: v1.3  
**文檔狀態**: ✅ 完整 (10+ 核心模組 PRD 已更新 + HTML 版)
