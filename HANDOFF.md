# HVAC Analytics 開發進度交接文件

**最後更新**: 2026-02-02 23:30 (UTC+8)

---

## 🎯 專案概述

這是一個 HVAC 冰水系統能耗分析與最佳化平台，用於：
1. 解析與清洗 HVAC 監控資料 (CSV)
2. 使用機器學習預測能耗
3. 優化變頻器設定以節省電力

---

## ✅ 已完成的功能

### Phase 1: ETL 管道 (100%)
- ✅ 資料解析器 (`src/etl/parser.py`) - 支援 2017/2018 格式
- ✅ 資料清洗器 (`src/etl/cleaner.py`) - 重採樣、異常偵測
- ✅ 批次處理器 (`src/etl/batch_processor.py`)
- ✅ Streamlit UI (`etl_ui.py`) - 完整的視覺化介面

### Phase 2: 機器學習與最佳化 (100%)
- ✅ XGBoost 能耗預測模型 (`src/models/energy_model.py`)
- ✅ 最佳化引擎 (`src/optimization/optimizer.py`) - SLSQP + DE
- ✅ CLI 介面 (`main.py`)

### Phase 3: 進階功能 (進行中)
- ✅ 歷史最佳化紀錄追蹤 (`src/optimization/history_tracker.py`)
- ✅ 時間特徵改善模型準確度 (MAPE 14.86% → 7.28%)
- ⏳ 熱平衡驗證整合
- ⏳ 親和力定律檢查整合

---

## 📊 模型效能

| 模型檔案 | 訓練資料 | MAPE | R² | 建議用途 |
|---------|---------|------|-----|----------|
| `energy_model.joblib` | 8 files (Jan 2017) | 4.55% | 0.9406 | 單月資料測試 |
| `energy_model_large.joblib` | 50 files (2017-2018) | 14.86% | 0.9598 | 跨季節基準 |
| **`energy_model_time_features.joblib`** | 50 files + 時間特徵 | **7.28%** | **0.9788** | ✅ **正式使用** |

---

## 🚀 快速啟動

### 1. 在新電腦上設定環境

```bash
# 克隆專案
git clone https://github.com/oscar120601/HVAC_Analytics.git
cd HVAC_Analytics

# 安裝依賴
pip install -r requirements.txt

# 安裝 XGBoost 需要的 OpenMP (macOS)
brew install libomp
```

### 2. 啟動 UI

```bash
python3 -m streamlit run etl_ui.py
```

### 3. 使用 CLI

```bash
# 解析資料
python main.py parse data/CGMH-TY/example.csv

# 訓練模型
python main.py train --data_dir data/CGMH-TY --n_files 50

# 執行最佳化
python main.py optimize models/energy_model_time_features.joblib
```

---

## 📂 重要檔案位置

| 檔案/目錄 | 用途 |
|----------|------|
| `etl_ui.py` | Streamlit 主程式 (UI) |
| `main.py` | CLI 主程式 |
| `src/models/energy_model.py` | 能耗預測模型 (含時間特徵) |
| `src/optimization/optimizer.py` | 最佳化引擎 |
| `src/optimization/history_tracker.py` | 歷史紀錄追蹤 |
| `models/` | 訓練好的模型檔案 |
| `data/CGMH-TY/` | 長庚醫院原始資料 |
| `.specify/specs/001-chiller-optimization/tasks.md` | 任務追蹤清單 |

---

## 🔧 未完成任務

1. **熱平衡驗證整合** - 將 `cleaner.py` 中的熱平衡檢查整合到訓練 Pipeline
2. **親和力定律檢查** - 驗證泵浦/風扇效能符合物理定律
3. **即時推薦儀表板** - 模擬即時資料流並自動推薦
4. **自動化警報** - 當違反物理限制時自動通知
5. **生產環境部署** - 部署到伺服器

---

## 📝 今日 (2026-02-02) 完成事項

1. ✅ **修復歷史紀錄儲存問題** - 使用 `session_state` 保存優化結果
2. ✅ **新增時間特徵** - 在模型中加入 hour, month, day_of_week, is_weekend
3. ✅ **重新訓練模型** - MAPE 從 14.86% 改善到 7.28% (↓51%)
4. ✅ **更新文件** - tasks.md, README.md

---

## 🔗 相關連結

- **GitHub Repo**: https://github.com/oscar120601/HVAC_Analytics
- **Spec-Kit 規格**: `.specify/specs/001-chiller-optimization/`

---

## 💡 接續開發建議

1. 優先完成「熱平衡驗證整合」，提升資料可信度
2. 考慮加入更多時間特徵 (如：節日、上班時間)
3. 嘗試不同的優化目標 (如：最小化成本而非能耗)
