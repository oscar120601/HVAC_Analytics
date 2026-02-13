# Optimization Engine PRD (v1.1) 最終核准報告

**審查對象**: `docs/Chiller_Plant_Optimization_Engine/PRD_Chiller_Plant_Optimization_V1.1.md`  
**關聯審查**: `docs/Model_Training/PRD_Model_Training_v1.2.md`  
**審查者**: Senior System Architect  
**日期**: 2026-02-13  
**總體評級**: **S (Production Ready)** - 架構完整，與 Training Pipeline 完美銜接，風險已排除。

---

## 1. 審查結論 (Executive Summary)

經過對 v1.1 版 PRD 的詳細審查，確認**所有關鍵架構風險（Granularity Gap）已完全解決**。

新引入的 **Model Registry Index** 機制成功地將「模型訓練」與「最佳化引擎」解耦，同時透過 **System-Level Blackbox** 策略確保了優化目標的可行性與準確性。

### ✅ 關鍵改進驗證 (Key Improvements Verified)

| 審查項目 | v1.0 狀態 | v1.1 狀態 | 評語 |
|:---|:---|:---|:---|
| **模型顆粒度** | 衝突 (Component vs System) | **一致 (System-Level Default)** | 雙方皆預設使用 `system_total_kw`，消除了架構歧義。 |
| **介面契約** | 模糊 (File Path 依賴) | **明確 (Registry Index)** | `model_registry_index.json` 成為單一真相來源，支援自動發現與版本驗證。 |
| **特徵對齊** | 未定義 | **嚴格 (FeatureVectorizer)** | 新增 `FeatureVectorizer` 類別，確保 Optimization Config 能精確轉換為模型所需的特徵向量。 |
| **混合模式** | 無 | **支援 (Hybrid Mode)** | 正確定義了 Hybrid 模式下的「一致性檢查」機制，兼顧了精度與可解釋性。 |
| **環境輸入** | 不明確 | **支援 (Ambient File)** | CLI 增加 `--ambient-file` 參數，滿足離線批次模擬需求。 |

---

## 2. 架構亮點 (Architectural Highlights)

1.  **Model Registry Index 作為契約核心**: 
    *   不僅解決了檔案路徑問題，還帶入 `schema_version` 與 `annotation_checksum`，在 Runtime 強制檢查版本相容性，防止了「模型與物理定義不一致」的災難性錯誤。

2.  **特徵向量化層 (Feature Vectorization Layer)**:
    *   明確將「設備配置 (Config)」轉換為「特徵向量 (Vector)」的責任劃分給 `FeatureVectorizer`，並繼承訓練時的 Scaler，這是確保模型預測有效性的關鍵設計。

3.  **雙軌約束引擎**:
    *   物理限制 (Physical Types) 與 邏輯約束 (Config Logic) 的分離設計非常清晰，且 v1.1 新增的 `min_runtime` / `switching_penalty` 有效解決了頻繁啟停的工程實務問題。

---

## 3. 實作建議 (Implementation Recommendations)

雖然文件已臻完美，但在 Coding 階段仍需注意以下細節：

### 3.1 優先順序
1.  **Phase 0 (介面層)**: 優先實作 `ModelRegistry` 與 `FeatureVectorizer`。這是連接兩大系統的橋樑，必須最先打通。
2.  **Phase 1 (約束層)**: 實作 `LogicConstraintGraph`。優化演算法若無約束檢查就是廢物，需優先保證產生出的解是「工程可行」的。
3.  **Phase 2 (優化層)**: 最後再實作 `HybridOptimizer`。初期甚至可以用簡單的 Random Search 替代 GA/DE，先驗證流程跑通。

### 3.2 測試策略
*   **Mock Registry**: 在測試 Optimization Engine 時，不要依賴真實的 Training 產出。請手刻一個 `mock_registry_index.json` 與 `mock_model.joblib`，確保單元測試的獨立性。
*   **Boundary Testing**: 重點測試 `FeatureVectorizer` 在邊界條件（如 load=0% 或 load=100%）下的數值轉換是否正確。

---

## 4. 結論

本 PRD (v1.1) 定義清晰、邏輯嚴密，且具備高度的可落地性。

**批准狀態**: **✅ APPROVED (正式核准)**

請立即進入 **Implementation Phase**，建議從 `src/optimization/model_interface.py` 開始構建。
