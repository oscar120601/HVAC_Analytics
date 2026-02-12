# HVAC Analytics - Core Engine

HVAC 冰水系統資料處理與分析的核心引擎，專注於 ETL 管道與能耗優化模型。

## 📁 專案結構

```
HVAC_Analytics/
├── src/                   # 核心模組
10: │   ├── etl/              # ETL 管道
11: │   │   ├── parser.py     # CSV 資料解析器
12: │   │   ├── cleaner.py    # 資料清洗與重採樣
13: │   │   └── batch_processor.py  # 批次處理器
14: │   ├── models/           # 機器學習模型
15: │   │   └── energy_model.py  # XGBoost 能耗預測模型
16: │   ├── optimization/     # 優化演算法
17: │   │   ├── optimizer.py  # SLSQP/DE 最佳化引擎
18: │   │   └── history_tracker.py  # 最佳化歷史追蹤
19: │   └── config/           # 配置系統
20: │       ├── feature_mapping.py       # 特徵映射配置 (V3)
21: │       └── feature_mapping_v2.py    # 特徵映射 V2
24: ├── data/                  # 資料目錄
28: ├── config/                # 配置檔案
29: ├── tests/                 # 單元測試
30: ├── main.py               # CLI 主程式
32: └── requirements.txt      # Python 依賴套件
```

## 📚 專案文檔

- **[v2.0]** [報表解析器重構 PRD](docs/evaluation/PRD.md) ([HTML版](docs/evaluation/PRD.html))
- **[v1.0]** [解析器評鑑報告](docs/evaluation/REPORT.md) ([PDF版](docs/evaluation/REPORT.pdf))

## 🚀 快速開始

### 使用 CLI

```bash
# 解析原始報表
python main.py parse data/raw/report.csv --output_file data/parsed/report.csv

# 訓練能耗預測模型
python main.py train data/clean/report.csv --model_output models/energy_model.pkl

# 執行最佳化
python main.py optimize models/energy_model.pkl '{"chw_pump_hz": 50, "cw_pump_hz": 50, "tower_fan_hz": 50}' '{"load_rt": 500, "temp_db_out": 85}'

# 使用特徵映射訓練
python main.py train data/CGMH-TY --mapping default

# 執行完整流程
python main.py pipeline data/raw/report.csv
```

## 🔧 核心功能

- **ETL 基礎建設**: 資料解析、清洗、批次處理、濕球溫度計算、凍結資料偵測。
- **能耗預測**: 基於 XGBoost 的高精度能耗建模。
- **最佳化引擎**: SLSQP 與全域優化 (Differential Evolution) 演算法。
- **特徵映射 (V3)**: 支援 HVAC 系統層級特徵對應。

## 📝 技術棧

- **資料處理**: Polars
- **機器學習**: scikit-learn, XGBoost
- **最佳化**: SciPy (SLSQP, Differential Evolution)
- **CLI**: Python Fire
