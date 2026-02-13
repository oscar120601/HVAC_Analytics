# HVAC Analytics - Core Engine (v1.2 Transition Phase)

**核心引擎狀態**: 🏗️ **架構轉型中 (Transition Phase)**  
我們正在從 v1.0 遷移至符合 `PRD System Integration v1.2` 的新架構。文件庫 (`docs/`) 已全面更新，但核心程式碼 (`src/`) 仍有部分基礎建設待實作。

## 🔍 專案概覽

HVAC 冰水系統資料處理與分析的核心引擎，專注於提供高可信度 (High-Fidelity) 的 ETL 管道與物理感知 (Physics-Aware) 的能耗優化模型。本專案核心目標是建立後端工程師可輕鬆整合的黑盒子模組。

## 📁 專案結構 (Target Architecture v1.2)

```
HVAC_Analytics/
├── src/                        # 核心源碼
│   ├── container.py            # [TODO] DI Container (系統心臟)
│   ├── context.py              # [TODO] Pipeline Context (時間基準)
│   ├── interface.py            # ★ Facade - 後端整合入口
│   ├── schemas.py              # Pydantic I/O 定義
│   ├── features/               # [TODO] 特徵管理
│   │   └── annotation_manager.py # Excel-to-YAML SSOT
│   ├── etl/                    # ETL 管道
│   │   ├── parser.py           # v2.1 報表解析 (E1xx Error Codes)
│   │   ├── cleaner.py          # v2.2 資料清洗 (E2xx Error Codes)
│   │   ├── batch_processor.py  # v1.3 批次處理
│   │   └── feature_engineer.py # [TODO] v1.3 特徵工程
│   ├── models/                 # 機器學習模型
│   │   └── energy_model.py     
│   ├── optimization/           # 優化演算法
│   │   ├── optimizer.py        
│   │   └── history_tracker.py  
│   └── utils/                  
│       └── config_loader.py    # [TODO] 統一配置載入
├── config/                     # 配置檔案
│   ├── settings.yaml           # 系統參數
│   └── features/               # [TODO] 案場特徵定義 (YAML SSOT)
├── docs/                       # 專案文檔 (全面更新)
│   ├── Interface Contract/     # ★ Master Interface Contract v1.0
│   ├── System Integration/     # System Integration v1.2
│   ├── parser/                 # Parser v2.1
│   ├── cleaner/                # Cleaner v2.2
│   └── ... (其他模組)
├── tests/                      # 單元測試
├── main.py                     # CLI 主程式
└── requirement.txt             # Python 依賴
```

## 📚 專案文檔 (已更新 2026-02-13)

所有 PRD 皆已升級以支援 Interface Contract v1.0 定義的 **E000-E999 錯誤代碼** 與 **Pipeline Timestamp** 機制。

### 核心架構
- **[System Integration v1.2](docs/System%20Integration/PRD_System_Integration_v1.2.html)** - 系統整合架構與初始化順序
- **[Interface Contract v1.0](docs/Interface%20Contract/PRD_INTERFACE_CONTRACT_v1.0.html)** - 全域錯誤代碼與時間基準規範

### 模組規格書
- **[Parser v2.1](docs/parser/PRD_Parser_V2.1.html)** - 強制 UTC 輸出與 E1xx 錯誤處理
- **[Cleaner v2.2](docs/cleaner/PRD_CLEANER_v2.2.html)** - 語意感知清洗與 E2xx 錯誤處理
- **[BatchProcessor v1.3](docs/batch_processor/PRD_BATCH_PROCESSOR_v1.3.html)** - Manifest 完整性與 E3xx 錯誤處理
- **[FeatureEngineer v1.3](docs/feature_engineering/PRD_FEATURE_ENGINEER_V1.3.html)** - Group Policy 與 E6xx 錯誤處理
- **[Hybrid Consistency v1.0](docs/Hybrid_Model_Consistency/PRD_Hybrid_Model_Consistency_v1.0.html)** - 混合模型一致性驗證 (E75x)

### 審閱報告
- **[架構重構報告](docs/restructuring/project_review_report_v1.0.md)** - 現況與目標差距分析

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

目前專案處於 **Phase 2: Code Implementation** 的初期階段：

- [x] **Phase 1**: PRD Alignment & Documentation Update (100%)
- [ ] **Phase 2**: Core Infrastructure (0%)
    - [ ] `src/context.py` (PipelineContext)
    - [ ] `src/container.py` (ETLContainer)
    - [ ] `src/utils/config_loader.py`
- [ ] **Phase 3**: Feature Management (0%)
    - [ ] `src/features/annotation_manager.py`
    - [ ] `excel_to_yaml` 轉換工具
- [ ] **Phase 4**: Module Refactoring (0%)
    - [ ] `parser.py` -> E1xx 支援
    - [ ] `cleaner.py` -> E2xx 支援

## 🤝 貢獻

請務必先閱讀 **[Interface Contract](docs/Interface%20Contract/PRD_INTERFACE_CONTRACT_v1.0.html)**，確保所有新代碼遵守錯誤代碼規範與時間基準邏輯。
