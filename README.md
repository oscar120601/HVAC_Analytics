# HVAC Analytics - 現代化冰水系統分析平台

HVAC 冰水系統資料處理與分析平台，採用現代化的前後端分離架構設計。

## 📁 專案結構

本專案已遷移至現代化的 **Client-Server 架構**，主要分為三個部分：

```
HVAC_Analytics/
├── frontend/              # ⚡ [新] 前端應用 (React + TypeScript)
│   ├── src/              # React 原始碼
│   └── ...
├── backend/               # 🚀 [新] 後端 API (FastAPI)
│   ├── main.py           # API 伺服器入口
│   └── ...
├── src/                   # 🧠 核心模組 (共用邏輯)
│   ├── etl/              # ETL 資料處理管道
│   ├── models/           # 機器學習模型
│   ├── optimization/     # 最佳化演算法
│   └── config/           # 配置系統 (Feature Mapping)
├── data/                  # 📊 資料目錄
│   ├── CGMH-TY/          
│   ├── Farglory_O3/      
│   └── kmuh/             
└── etl_ui.py             # 🐢 [舊] Streamlit UI (Legacy)
```

## 🚀 快速開始

### 1. 啟動後端 API (Backend)

後端提供 RESTful API 服務，負責處理資料、執行模型與最佳化運算。

```bash
cd backend

# Windows 啟動腳本 (自動設定環境)
start_server.bat

# 或手動啟動
# python -m venv .venv
# .venv\Scripts\activate
# pip install -r requirements.txt
# python main.py
```

伺服器將啟動於: `http://localhost:8000`  
API 文件: `http://localhost:8000/docs`

### 2. 啟動前端介面 (Frontend)

現代化的 Web 介面，提供更流暢的操作體驗與視覺化效果。

```bash
cd frontend

# 安裝依賴 (初次執行)
npm install

# 啟動開發伺服器
npm run dev
```

應用程式將啟動於: `http://localhost:3000`

### 3. 繼承模式 (Legacy Mode)

如果您仍需使用舊版的 Streamlit 介面：

```bash
# Windows/Linux
bash start_ui.sh

# 或
python -m streamlit run etl_ui.py
```

## ✨ 主要功能

### 🌩️ 現代化架構
- **前後端分離**: React 18 前端 + FastAPI 高效能後端
- **即時回應**: 使用非同步處理提升操作流暢度
- **模組化設計**: 核心邏輯 (`src/`) 可被前後端與 CLI 共用

### ⚡ 最佳化模擬 (Optimization Simulation)
- **🗺️ 特徵映射 V3 (Feature Mapping)**: 
  - 支援 **13 種物理系統分類** (冰水機、泵浦、冷卻水塔等)
  - 支援 **萬用字元模式** (`CH_*_RT`) 快速配置大量欄位
  - 提供 **自動識別** 功能
- **🎯 即時最佳化**: 調整運轉參數，即時預估能耗變化
- **📊 特徵重要性**: 分析影響能耗的關鍵因子
- **📈 歷史追蹤**: 記錄並比較多次模擬結果

### 🧹 資料 ETL 處理
- **批次處理**: 支援多檔案合併與自動化清洗
- **智慧清洗**: 自動偵測凍結值、穩態運轉點
- **物理驗證**: 熱平衡 (Heat Balance) 與親和力定律 (Affinity Laws) 檢查

## 🛠️ 技術堆疊

- **前端**: React 18, TypeScript, Tailwind CSS, shadcn/ui, Vite
- **後端**: Python, FastAPI, Uvicorn
- **資料處理**: Polars (高效能 DataFrame), NumPy, Pandas
- **機器學習**: XGBoost, scikit-learn
- **最佳化**: SciPy (SLSQP, Differential Evolution)

## 📝 開發指南

### 新增功能
建議優先在 `src/` 中開發核心邏輯，確保能被 Backend API 與 Legacy UI 同時使用。

### 文件資源
- `backend/README.md`: 後端 API 詳細說明
- `frontend/README.md`: 前端開發指南
- `FEATURE_MAPPING_V2_GUIDE.md`: 特徵映射 V3 配置手冊
