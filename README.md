# HVAC Analytics - ETL Pipeline

HVAC 冰水系統資料處理與分析平台

## 📁 專案結構

```
HVAC_Analytics/
├── .specify/              # Spec-Kit 配置
├── src/                   # 核心模組
│   ├── etl/              # ETL 管道
│   │   ├── parser.py     # CSV 資料解析器
│   │   ├── cleaner.py    # 資料清洗與重採樣
│   │   └── batch_processor.py  # 批次處理器
│   ├── models/           # 機器學習模型
│   │   └── energy_model.py  # XGBoost 能耗預測模型
│   ├── optimization/     # 優化演算法
│   │   └── optimizer.py  # SLSQP/DE 最佳化引擎
│   └── config/           # 配置系統
│       └── feature_mapping.py  # 特徵映射配置 (V2)
├── data/                  # 資料目錄
│   ├── CGMH-TY/          # 長庚醫院台北資料
│   ├── Farglory_O3/      # 遠雄 O3 案場資料
│   └── kmuh/             # 其他案場資料
├── config/                # 配置檔案
├── tests/                 # 單元測試
├── main.py               # CLI 主程式
├── etl_ui.py             # Streamlit UI 主程式
├── requirements.txt      # Python 依賴套件
└── start_ui.sh           # 啟動腳本

## 🚀 快速開始

### 1. 啟動 Streamlit UI

```bash
# 使用啟動腳本
bash start_ui.sh

# 或直接執行
python3 -m streamlit run etl_ui.py
```

### 2. 使用 CLI

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

### 3. 特徵映射配置 (Feature Mapping V3)

批次處理完成後，使用視覺化界面配置特徵映射：

**自動識別**: 系統自動識別 13 種標準特徵類別（按 HVAC 物理系統分組）

**❄️ 冰水側系統 (Chilled Water Side) - 6個類別:**
- `chiller` - 冰水機 ❄️ - 負載、溫度、流量、功率
- `chw_pump` - 冰水泵 💧 - 頻率、功率、用電量
- `scp_pump` - 區域泵/二次泵 🔄 - 頻率、功率、用電量
- `chw_temp` - 冰水溫度 🌡️ - 供水/回水/溫差
- `chw_pressure` - 冰水壓力 📊 - 供水/回水/壓差
- `chw_flow` - 冰水流量 🌊 - LPM

**🔥 冷卻水側系統 (Condenser Water Side) - 4個類別:**
- `cw_pump` - 冷卻水泵 🔥 - 頻率、功率、用電量
- `cw_temp` - 冷卻水溫度 🌡️ - 供水/回水/溫差
- `cw_pressure` - 冷卻水壓力 📊 - 供水/回水/壓差
- `cw_flow` - 冷卻水流量 🌊 - LPM

**🏭 冷卻水塔系統 (Cooling Tower) - 1個類別:**
- `cooling_tower` - 冷卻水塔 🏭 - 風扇頻率、功率、趨近溫度

**🌍 環境參數 (Environment) - 1個類別:**
- `environment` - 環境參數 🌍 - 外氣溫度、濕度、濕球溫度

**⚡🎯 系統層級 (System Level) - 1個類別:**
- `system_level` - 系統效率指標 ⚡🎯 - 總用電、COP、kW/RT

**三種配置方式**: 自動識別 / 手動對應 / 萬用字元模式

**自定義類別**: 支援新增無限自定義特徵類別

**JSON 匯出**: 儲存配置供日後使用

```bash
# 使用預設映射
python main.py train data/CGMH-TY --mapping default

# 使用自定義映射檔案
python main.py train data/CGMH-TY --mapping my_mapping.json
```

### 4. UI 功能

- **單一檔案模式**: 上傳或選擇單一 CSV 檔案進行分析
- **批次處理模式**: 選擇多個檔案批次處理並合併
- **特徵映射配置(新)**: 視覺化配置 13 種特徵類別（按 HVAC 物理系統分組），支援萬用字元模式與自定義類別
- **最佳化模擬**: 調整變頻器參數，即時預估能耗與節能效益
- **模型管理(新)**: 已訓練模型列表管理與刪除功能
- **統計資訊**: 數值分佈、平均值、標準差等統計指標
- **時間序列**: 多變數時間序列視覺化
- **關聯矩陣**: 變數相關性熱圖與強度分析
- **資料品質**: 缺失值分析、凍結偵測與品質評分
- **資料匯出**: CSV / Parquet 格式匯出

## 📊 資料格式

支援特殊格式的 HVAC 監控 CSV：
- Metadata Tag Mapping
- Pre-pivoted Data Format
- 自動合併處理重複時間戳

## 🔧 開發狀態

### ✅ Phase 1 - ETL 基礎建設 (100% 完成)
- [x] 資料解析器
- [x] 資料清洗器
- [x] 批次處理功能
- [x] 統一 UI 設計
- [x] 時間序列視覺化
- [x] 濕球溫度計算
- [x] 凍結資料偵測
- [x] 關聯矩陣熱圖
- [x] 資料品質儀表板

### ✅ Phase 2 - 機器學習與最佳化 (100% 完成)
- [x] XGBoost 能耗預測模型 (MAPE < 5% for single-season)
- [x] SLSQP 最佳化引擎與全域優化 (Differential Evolution)
- [x] 物理限制驗證（壓差、溫度、頻率）
- [x] 最佳化模擬 UI 介面整合 (Streamlit)
- [x] 2018 CSV 解析相容性修復
- [x] 特徵重要性分析
- [x] 模型持久化（joblib）
- [x] CLI 介面完整實作

### ✅ Phase 3 - 進階分析與部署 (已完成)
- [x] 歷史最佳化紀錄追蹤 (history_tracker.py)
- [x] 時間特徵優化 (MAPE 14.86% → 7.28%)
- [x] 優化資料清洗策略 (Smart Aggregation)
- [x] 熱平衡驗證整合 (CLI & UI)
- [x] 親和力定律檢查整合 (CLI & UI) ✅ 2026-02-03
- [x] 批次處理物理驗證選項 (穩態/熱平衡/親和力) ✅ 2026-02-03
- [x] **Feature Mapping V3** - 支援 13 種 HVAC 物理系統層級特徵類別與萬用字元模式 ✅ 2026-02-10
- [x] **資料型態修正** - 解決批次處理數字轉字串問題 ✅ 2026-02-09
- [x] **模型管理** - 已訓練模型刪除功能 ✅ 2026-02-09

### 🔜 Phase 4 - 未來規劃
- [ ] 實時推薦系統
- [ ] 自動化警報系統
- [ ] 部署至上線環境

### 📈 模型效能

| 模型 | MAPE | R² | 說明 |
|------|------|-----|------|
| energy_model.joblib | 4.55% | 0.9406 | 單季資料 (8 files) |
| energy_model_large.joblib | 14.86% | 0.9598 | 跨季資料 (50 files) |
| **energy_model_time_features.joblib** | **7.28%** | **0.9788** | ✅ 最佳模型 |

## 📝 技術棧

- **資料處理**: Polars (高效能)
- **UI 框架**: Streamlit
- **視覺化**: Plotly
- **機器學習**: scikit-learn, XGBoost
- **最佳化**: SciPy (SLSQP, Differential Evolution)
- **CLI**: Python Fire

