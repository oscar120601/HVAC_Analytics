# Optimization Engine PRD (v1.0) 審查報告

**審查對象**: `docs/Chiller_Plant_Optimization_Engine/PRD_Chiller_Plant_Optimization_V1.0.md`  
**參考文件**: 
- `docs/Model_Training/PRD_Model_Training_v1.1.md`
- `docs/Feature_Annotation_Specification/PRD_Feature_Annotation_Specification_V1.2.md`
**審查者**: Senior System Architect  
**日期**: 2026-02-13  
**總體評級**: **A- (Architectural Mismatch Identified)** - 架構設計完善，但在模型顆粒度上與上游 Training PRD 存在關鍵落差。

---

## 1. 總體評鑑 (Overall Assessment)

Optimization PRD v1.0 提出了一個強大的混合優化架構（MIP + 連續優化），並正確引用了 Feature Annotation 的物理限制與多案場配置概念。邏輯約束引擎（Logic Constraint Engine）的設計尤為出色，能有效處理冰水主機房複雜的設備依賴關係。

然而，**模型訓練 (Training)** 與 **最佳化 (Optimization)** 之間存在一個關鍵的**介面/顆粒度落差**，若不解決將導致系統無法運作。

### ✅ 強項 (Strengths)
1.  **邏輯約束優先**: 將物理開關機邏輯（Requires, Mutex, Sequence）與能耗優化分離，確保建議具備工程可行性。
2.  **混合優化策略**: 針對離散變數（啟停）與連續變數（頻率）分階段處理，兼顧了求解效率。
3.  **離線報告模式**: 清楚定義了 Input/Output，避免了與即時控制系統 (DDC) 整合的高風險。
4.  **配置繼承機制**: 沿用 Feature Annotation 的繼承模式，利於多案場維護。

---

## 2. 關鍵風險：模型顆粒度不匹配 (The Granularity Gap)

這是本次審查發現的最嚴重問題，必須在實作前修正。

### 2.1 問題描述
*   **Model Training PRD v1.1**: 設計為 **"Single Target, Multi-Algorithm"**。
    *   它訓練的是**一個目標變數**（例如 `System Total Power` 或 `Chiller 1 Power`），使用三種演算法（XGB, LGB, RF）進行 Ensemble。
    *   產出物 `MultiModelArtifact` 代表**一個預測目標**的最佳模型組合。
*   **Optimization PRD v1.0**: 假設擁有 **"Component-Level Models"**。
    *   Config 範例 (Line 147, 155) 引用了 `model_file: "chiller_1_model.joblib"`, `model_file: "chiller_2_model.joblib"`。
    *   這暗示優化引擎需要分別預測每台設備的能耗，然後加總。

### 2.2 衝突點
若我們只跑一次 Training Pipeline 訓練 `Total Power`，則 Optimization Engine 無法載入個別設備模型。若我們要分別預測，則需要針對每台設備**分別執行** Training Pipeline，並產生多個 Artifacts。

### 2.3 建議解決方案 (二選一)

#### 方案 A：系統級黑盒優化 (System-Level Blackbox) - **推薦**
*   **概念**: 訓練**單一**模型預測 `Total System kW`。
*   **特徵**: 輸入特徵必須包含所有控制變數（如 `chiller_1_status`, `pump_1_hz`, `ct_1_speed`）。
*   **修改點**: 
    1.  Optimization Config 移除個別設備的 `model_file` 欄位。
    2.  `ModelRegistry` 載入單一 `MultiModelArtifact`。
    3.  目標函數直接呼叫該模型預測總耗電。
*   **優點**: 簡單，符合 Training PRD 現狀，考慮了設備間的交互作用（Copula effect）。
*   **缺點**: 無法得知單機細節耗電（除非模型有做多輸出，但目前沒有）。

#### 方案 B：組件級加總優化 (Component-Level Summation)
*   **概念**: 對每台 Chiller, Pump, CT **分別訓練**模型。
*   **修改點**:
    1.  Training Pipeline 需支援批次訓練多個 Targets。
    2.  Artifacts 儲存結構需改為 `models/{site_id}/{target_name}/...`。
*   **優點**: 可針對個別設備效率進行診斷。
*   **缺點**: 忽略了系統耦合效應，維護成本高（N 個設備 = N 個模型）。

**架構師建議**: 採用 **方案 A**。對於總耗電優化，系統級模型通常更準確且易於維護。

---

## 3. 其他優化建議

### 3.1 輸入數據來源不明確
*   **問題**: 優化需要 `ambient_conditions`（外氣濕球/乾球溫度）。PRD 若為「離線建議」，這些數據從何而來？
*   **建議**: 
    *   增加 `ScenarioLoader`，支援從歷史 CSV 讀取一段時間的外氣條件進行批次模擬。
    *   或在 CLI 支援 `--ambient-file weather.csv`。

### 3.2 效率曲線 (Efficiency Curve) 的角色
*   **問題**: Config 中定義了 `efficiency_curve` (Line 164)，但同時又有 ML 模型。
*   **建議**: 明確定義優先級。通常 ML 模型準確度高於原廠曲線。建議將 `efficiency_curve` 作為 **Fallback**（當 ML 模型預測信心不足或超出範圍時使用），或作為物理約束的邊界參考。

### 3.3 設備啟停頻率懲罰
*   **問題**: 純數學優化可能會建議頻繁啟停（例如這小時開，下小時關）。
*   **建議**: 在目標函數中加入 `switching_penalty`（切換懲罰項），或在邏輯約束中加入 `min_runtime` / `min_downtime`（最小運行/停機時間）。

---

## 4. 修正行動清單 (Action Items)

請在開始 Coding 前更新 PRD v1.0：

1.  **[Critical] 修正模型載入邏輯**: 
    *   確認採用「方案 A（系統級模型）」或「方案 B（組件級模型）」。
    *   若選 A，修改 Config 結構，將 `model_file` 移至全域設定，並註明模型輸入特徵需求。
2.  **[Major] 增強輸入介面**: 
    *   在 `OptimizationCLI` 增加批次天氣資料輸入支援。
3.  **[Minor] 補充啟停約束**: 
    *   在 `LogicConstraintGraph` 增加 `min_runtime` 支援。

---

**結論**: 
此 PRD 邏輯清晰，但在與 Training 模組的銜接點上有架構落差。請針對 **Section 2.3** 做出決策並更新文件後，即可批准執行。
