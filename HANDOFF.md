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
3. **優化資料清洗策略** - 修正重採樣邏輯：KWH 應取 `last()`，狀態/故障訊號應取 `max()`，而非全面使用 `mean()`
4. **即時推薦儀表板** - 模擬即時資料流並自動推薦
5. **自動化警報** - 當違反物理限制時自動通知
6. **生產環境部署** - 部署到伺服器

---

## 📝 今日 (2026-02-02) 完成事項

1. ✅ **修復歷史紀錄儲存問題** - 使用 `session_state` 保存優化結果
2. ✅ **新增時間特徵** - 在模型中加入 hour, month, day_of_week, is_weekend
3. ✅ **重新訓練模型** - MAPE 從 14.86% 改善到 7.28% (↓51%)
4. ✅ **更新文件** - tasks.md, README.md

## 📝 今日 (2026-02-03) 完成事項

1. ✅ **改善 UI 體驗** - 在「最佳化模擬」模式中，即使未選擇模型也能顯示分頁，方便直接進行模型訓練
2. ✅ **修復資料預覽** - 過濾掉 CSV 報表中的無效分隔線 (`**********`)
3. ✅ **修正資料品質分析** - 批次處理模式下排除 Date/Time 欄位的缺失值計算
4. ✅ **優化資料清洗策略** - 修正重採樣邏輯：KWH 改用 `last()` 保留累計值，狀態值改用 `max()` 捕捉運轉狀態

---

## 🔗 相關連結

- **GitHub Repo**: https://github.com/oscar120601/HVAC_Analytics
- **Spec-Kit 規格**: `.specify/specs/001-chiller-optimization/`

---

## 💡 接續開發建議 (Domain Expert Roadmap)
1. 優先完成「熱平衡驗證整合」，提升資料可信度
2. 下一階段重點任務 (Phase 5):
    *   **物理模型強化**: 加入 Lift (揚程), Approach (趨近溫度), PLR (部分負載率) 等特徵。
    *   **資料品質提升**: 實作穩態偵測 (Steady State Detection) 與強制熱平衡過濾。
    *   **控制安全保護**: 增加流量下限保護 (Min Flow GPM) 與防震盪 (Anti-Hunting) 控制。
    *   **商業價值優化**: 將優化目標從 kW 轉為 Cost ($)，整合時間電價 (TOU) 策略。
