# HVAC Analytics - Core Engine

HVAC 冰水系統資料處理與分析的核心引擎，專注於 ETL 管道與能耗優化模型。

## 📁 專案結構

```
HVAC_Analytics/
├── src/                   # 核心模組
│   ├── interface.py       # ★ Facade - 後端整合入口
│   ├── schemas.py         # Pydantic I/O 定義
│   ├── exceptions.py      # 自定義例外
│   ├── etl/              # ETL 管道
│   │   ├── parser.py     # CSV 資料解析器
│   │   ├── cleaner.py    # 資料清洗與重採樣
│   │   └── batch_processor.py  # 批次處理器
│   ├── models/           # 機器學習模型
│   │   └── energy_model.py  # XGBoost 能耗預測模型
│   ├── optimization/     # 優化演算法
│   │   ├── optimizer.py  # SLSQP/DE 最佳化引擎
│   │   └── history_tracker.py  # 最佳化歷史追蹤
│   ├── config/           # 配置系統
│   │   └── feature_mapping.py  # 特徵映射配置
│   └── utils/            # 工具模組
│       └── logger.py     # 統一日誌
├── config/               # 配置檔案
│   ├── settings.yaml     # 系統參數
│   └── hvac_feature_classification.json  # 特徵分類
├── docs/                 # 專案文檔
│   ├── evaluation/       # 評鑑報告
│   └── restructuring/    # 重構文檔
├── scripts/              # 工具腳本
├── tests/                # 單元測試
├── main.py              # CLI 主程式
├── pyproject.toml       # Python 專案配置
└── requirements.txt     # Python 依賴套件
```

## 📚 專案文檔

### 核心文檔
- **[重構審閱](docs/restructuring/review_restructuring_proposal.md)** - 專案架構重構分析
- **[驗證報告](docs/restructuring/verification_report.md)** - 重構完成度驗證

### 評鑑報告
- **[v2.0 PRD](docs/evaluation/PRD.md)** ([HTML](docs/evaluation/PRD.html)) - 報表解析器重構產品需求文件
- **[v1.0 評鑑報告](docs/evaluation/REPORT.md)** ([PDF](docs/evaluation/REPORT.pdf)) - 解析器評鑑分析

## 🚀 快速開始

### 方式 1: 使用 Facade 介面（推薦給後端整合）

```python
from src.interface import HVACService
from src.schemas import OptimizationContext

# 初始化服務
service = HVACService()

# 載入訓練好的模型
service.load_model("models/energy_model.joblib")

# 執行最佳化
context = OptimizationContext(
    load_rt=500.0,
    temp_db_out=30.0
)
result = service.optimize(context)

print(f"節能潛力: {result.savings_percent:.1f}%")
```

### 方式 2: 使用 CLI

```bash
# 解析原始報表
python main.py parse data/raw/report.csv --output data/parsed/report.csv

# 訓練能耗預測模型
python main.py train data/clean/ --model_output models/energy_model.joblib

# 執行最佳化
python main.py optimize models/energy_model.joblib \
  '{"chw_pump_hz": 50, "cw_pump_hz": 50, "tower_fan_hz": 50}' \
  '{"load_rt": 500, "temp_db_out": 30}'

# 使用特徵映射訓練
python main.py train data/CGMH-TY --mapping default

# 執行完整流程
python main.py pipeline data/raw/report.csv
```

## 🔧 核心功能

- **ETL 基礎建設**: 資料解析、清洗、批次處理、濕球溫度計算、凍結資料偵測
- **能耗預測**: 基於 XGBoost 的高精度能耗建模
- **最佳化引擎**: SLSQP 與全域優化 (Differential Evolution) 演算法
- **特徵映射**: 支援 HVAC 系統層級特徵對應
- **介面層**: 提供統一的 Facade 模式，簡化後端整合

## 🏗️ 架構特色

### 對接層設計

本專案採用 **Facade 模式**，將複雜的內部邏輯封裝為簡單的 API：

- **`src/interface.py`**: 統一的服務入口點 (`HVACService`)
- **`src/schemas.py`**: Pydantic 資料模型，確保型別安全與自動驗證
- **`src/exceptions.py`**: 標準化錯誤處理

### 模組化設計

- **獨立模組**: ETL、模型、優化各自獨立，可單獨測試與維護
- **統一日誌**: `src/utils/logger.py` 提供一致的日誌格式
- **配置分離**: 配置檔與程式碼分離，支援多案場部署

## 📝 技術棧

- **資料處理**: Polars
- **機器學習**: scikit-learn, XGBoost
- **最佳化**: SciPy (SLSQP, Differential Evolution)
- **CLI**: Python Fire
- **資料驗證**: Pydantic
- **配置管理**: PyYAML

## 🧪 測試

```bash
# 執行所有測試
pytest tests/

# 執行特定測試
pytest tests/test_energy_model.py
```

## 📦 安裝

```bash
# 使用 pip
pip install -e .

# 或使用 requirements.txt
pip install -r requirements.txt
```

## 👥 貢獻指南

請參考 [CONTRIBUTING.md](CONTRIBUTING.md) 瞭解如何貢獻程式碼。

## 📄 授權

本專案採用 MIT 授權條款。
