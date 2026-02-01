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
│   ├── models/           # (未來) 機器學習模型
│   └── optimization/     # (未來) 優化演算法
├── data/                  # 資料目錄
│   ├── CGMH-TY/          # 長庚醫院台北資料
│   ├── Farglory_O3/      # 遠雄 O3 案場資料
│   └── kmuh/             # 其他案場資料
├── config/                # 配置檔案
├── tests/                 # 單元測試
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

### 2. UI 功能

- **單一檔案模式**: 上傳或選擇單一 CSV 檔案進行分析
- **批次處理模式**: 選擇多個檔案批次處理並合併
- **統計資訊**: 數值分佈、平均值、標準差等統計指標
- **時間序列**: 多變數時間序列視覺化
- **資料匯出**: CSV / Parquet 格式匯出

## 📊 資料格式

支援特殊格式的 HVAC 監控 CSV：
- Metadata Tag Mapping
- Pre-pivoted Data Format
- 自動合併處理重複時間戳

## 🔧 開發狀態

### ✅ Phase 1 - ETL 基礎建設 (95% 完成)
- [x] 資料解析器
- [x] 資料清洗器
- [x] 批次處理功能
- [x] 統一 UI 設計
- [x] 時間序列視覺化
- [ ] 關聯矩陣熱圖
- [ ] 資料品質儀表板

### 🔜 Phase 2 - 進階分析
- [ ] 異常偵測規則
- [ ] 效能分析指標
- [ ] 關聯性分析

### 🤖 Phase 3 - 機器學習
- [ ] 特徵標注系統
- [ ] 異常偵測模型 (Isolation Forest)
- [ ] 能耗預測 (XGBoost/Random Forest)

## 📝 技術棧

- **資料處理**: Polars (高效能)
- **UI 框架**: Streamlit
- **視覺化**: Plotly
- **機器學習**: scikit-learn, XGBoost (Phase 3)
