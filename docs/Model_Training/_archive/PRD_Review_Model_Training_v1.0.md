# Model Training PRD (v1.0) 審查與評鑑報告

**審查對象**: `docs/MODEL_TRAINING/PRD_MODEL_TRAINING_v1.0.md`  
**審查者**: Senior Data Architect / AI Lead  
**日期**: 2026-02-13  
**總體評級**: **S (Excellent)** - 架構嚴謹，與上游整合度極高，適合大規模部署。

---

## 1. 總體評鑑 (Overall Assessment)

這份 PRD 展示了極高水準的系統架構設計，完美地將機器學習的最佳實踐（Best Practices）與本專案的特殊需求（HVAC 物理特性、SSOT 架構）結合。

### ✅ 核心優勢 (Key Strengths)
1.  **多模型競賽架構 (Champion-Challenger Strategy)**:
    *   同時支援 XGBoost (精度)、LightGBM (速度)、Random Forest (鲁棒性)，並自動選擇最佳模型。這對於 HVAC 領域非常關鍵，因為不同案場的資料特性差異巨大，單一模型往往難以通吃。
2.  **與 Feature Annotation 深度整合**:
    *   不僅是被動接收資料，更主動利用 `device_role` 進行樣本加權 (Sample Weighting) 與分層，這是領域知識 (Domain Knowledge) 結合 AI 的典範。
    *   嚴格的版本綁定 (`annotation_context`) 確保了模型的可追溯性 (Reproducibility)。
3.  **零資料洩漏 (Zero Data Leakage)**:
    *   嚴格的 `temporal_cutoff` 檢查與輸入契約驗證，從源頭杜絕了由未來資料導致的模型虛高 (Look-ahead Bias)。
4.  **工程化思維**:
    *   包含 `ProcessPoolExecutor` 平行訓練、記憶體優化 (LightGBM Dataset)、以及完整的錯誤代碼體系 (E6xx/E7xx)，展現了對生產環境穩定性的重視。

### ⚠️ 潛在風險與挑戰 (Risks & Challenges)

雖然架構優秀，但在實際落地時仍有以下挑戰：

| 風險項目 | 影響 | 建議緩解措施 |
|:---|:---|:---|
| **記憶體爆炸 (OOM)** | 平行訓練 3 個模型（尤其是 Random Forest 與 XGBoost）極耗記憶體，可能導致 Container 崩潰。 | 1. 實作動態資源檢測，記憶體不足時自動降級為序列訓練。<br>2. 限制 `n_jobs`，避免 CPU 搶佔。 |
| **可解釋性不足** | 目前僅輸出 Feature Importance (Gain/Split)，這對於現場工程師來說不夠直觀（他們想知道"為什麼預測這台主機耗電高？"）。 | **建議 v1.1 加入 SHAP (SHapley Additive exPlanations)** 整合，提供單筆預測的歸因分析。 |
| **超參數搜尋複雜度** | PRD 雖提及 Optuna，但在 Phase 2 實作細節中較少著墨。若開啟搜尋，訓練時間將從分鐘級暴增至小時級。 | 建議將 Hyperparameter Search 獨立為一個可選的 "這一夜訓練 (Overnight Training)" 模式，日常開發使用預設參數。 |

---

## 2. 細部審查 (Detailed Review)

### 2.1 介面契約 (Interface Alignment)
*   **輸入契約**: 與 `FeatureEngineer v1.3-FA` 的輸出高度一致。特別是 `annotation_context` 的傳遞路徑（Cleaner -> BP -> FE -> Model）非常清晰。
*   **錯誤處理**: E6xx 系列錯誤代碼定義明確，能有效攔截上游問題。

### 2.2 模型配置 (Model Configuration)
*   **XGBoost**: 預設 `tree_method="hist"` 是正確選擇，對大數據更友善。
*   **LightGBM**: 預設 `boosting_type="gbdt"` 穩健，參數設置合理。
*   **Random Forest**: 預設啟動 `oob_score` 是亮點，提供了額外的驗證指標。

### 2.3 程式碼實作 (Implementation Plan)
*   **BaseModelTrainer**: 抽象層設計良好，強制實作 `train`, `predict`, `get_feature_importance`，便於未來擴充其他模型（如 Neural Networks）。
*   **TrainingPipeline**: 邏輯清晰，包含完整的訓練-評估-選擇迴圈。

---

## 3. 修正建議 (Recommendations)

### 3.1 短期修正 (v1.0 實作階段)
1.  **資源保護機制**:
    *   在 `train_all_models` 中加入簡單的 `psutil` 檢查，若可用記憶體 < 總記憶體 30%，強制切換為序列訓練 (`parallel_training=False`)。
2.  **資料量防護**:
    *   將 E607 (n_samples >= 100) 的閾值對應不同模型調整。例如 LightGBM 通常需要 >1000 筆資料才能發揮優勢，否則易過擬合；RF 對小樣本較友善。

### 3.2 長期規劃 (v1.1+)
1.  **SHAP 整合**: 產出 `shap_summary_plot.png` 與 `shap_values.npy`，作為模型交付物的一部分。
2.  **增量學習 (Incremental Learning)**: 利用 XGBoost/LightGBM 的 `init_model` 或 RF 的 `warm_start`，支援新資料的快速迭代。

---

## 4. 結論 (Conclusion)

這份文件**完全適合 (Highly Suitable)** 本專案。它不僅是一個執行腳本的規格書，更是一個具備容錯、稽核與自動化能力的 ML 系統藍圖。

**批准狀態**: **✅ APPROVED (建議採納)**

請依據此 PRD 進入開發階段，並優先實作 `BaseModelTrainer` 與 `TrainingPipeline` 骨架。
