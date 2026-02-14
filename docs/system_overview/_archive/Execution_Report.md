# HVAC Analytics 系統全方位執行報告 (System Execution Report)

本報告基於 `docs/` 目錄下所有核心 PRD (v1.0 ~ v2.2) 進行綜合分析，旨在為開發團隊提供一套嚴謹、無縫銜接的實作藍圖。

---

## 1. 執行摘要 (Executive Summary)

本專案的核心目標是建構一套**「物理感知 (Physics-Aware)」**且**「契約驅動 (Contract-Driven)」**的 HVAC 數據分析系統。

經過對 12+ 份 PRD 的深度解析，本系統的架構建立在三個不可動搖的支柱上：

1.  **SSOT 絕對權威**: 所有的特徵定義 (Feature Annotation) 來自 Excel，所有的優化限制 (Constraints) 來自 Optimization Config。任何模組不得私自定義這些規則。
2.  **時空一致性 (Spatio-Temporal Consistency)**: 透過 `PipelineContext` 鎖定時間基準，並透過 `EquipmentValidator` 將物理限制逆向同步至 ETL 階段，確保「數據流」與「物理流」的一致。
3.  **防禦性架構 (Defensive Architecture)**: 從 `Wizard` 的技術阻擋 (防止亂改 Config) 到 `Interface Contract` 的嚴格檢查點，系統假設 inputs are guilty until proven innocent。

---

## 2. 核心模組架構與 PRD 映射 (Module Architecture)

### 2.1 基礎設施層 (Infrastructure Layer)

| 模組 | 關鍵 PRD | 核心職責 | 關鍵機制 |
| :--- | :--- | :--- | :--- |
| **Feature Annotation** | `Feature_Annotation_Specification_V1.2` | 定義點位、物理類型、設備角色。系統唯一的 Domain Knowledge 來源。 | **Excel-Centric SSOT**: 僅允許編輯 Excel，透過 `excel_to_yaml.py` 轉為 YAML 供程式讀取。 |
| **Wizard Blockade** | `Wizard_Technical_Blockade_V1.0` | **[New]** 保護 SSOT 不被繞過。 | **Runtime Import Hook**: 禁止 `import yaml`。<br>**Filesystem Guard**: YAML 檔設為 444 唯讀。<br>**Pre-commit**: 阻擋直接修改 YAML 的 Commit。 |
| **System Integration** | `System_Integration_v1.2` | **[New]** 串聯所有模組，管理生命週期。 | **PipelineContext**: 統一全域時間戳 (UTC)，防止未來資料漂移。<br>**Container**: 嚴格初始化順序 (Config -> Lock -> Manager -> Modules)。 |

### 2.2 ETL 數據處理層 (Data Processing Layer)

| 模組 | 關鍵 PRD | 接收輸入 | 產出 | 關鍵邏輯 |
| :--- | :--- | :--- | :--- | :--- |
| **Parser** | `Parser_V2.1` | Raw CSV/Excel | DF (UTC, UTF-8) | **時區強制**: 所有時間轉 UTC。<br>**編碼偵測**: 自動處理 BOM/Big5。<br>**契約**: 檢查點 #1。 |
| **Cleaner** | `CLEANER_v2.2` | Parser DF | Cleaned DF | **語意感知**: 讀取 Annotation 知道哪些是「備機」，調整清洗策略。<br>**物理驗證**: 呼叫 `EquipmentValidator` 標記物理不可能的數據 (E351)。 |
| **Validation** | `Equipment_Dependency_Validation_v1.0` | Cleaner Row | Quality Flags | **[New] 反向同步**: 讀取 `Optimization Config`，在 ETL 階段就抓出「開主機沒開泵」等邏輯錯誤。 |
| **Batch Processor** | `BATCH_PROCESSOR_v1.3` | Cleaned DF | Manifest + Parquet | **稽核軌跡**: 記錄 Annotation Version 與 Checksum。<br>**時序驗證**: 計算開關機順序錯誤 (E353)。 |
| **Feature Engineer** | `FEATURE_ENGINEER_V1.3` | Manifest | Feature Matrix | **Group Policy**: 根據物理類型自動生成特徵 (Lags, Windows)。<br>**Leakage Prevention**: 嚴格排除 `device_role` 進入模型輸入。 |

### 2.3 模型與優化層 (Modeling & Optimization Layer)

| 模組 | 關鍵 PRD | 核心職責 | 關鍵機制 |
| :--- | :--- | :--- | :--- |
| **Model Training** | `Model_Training_v1.2` | 訓練系統/組件模型 | **Registry**: 標準化模型產出。<br>**Resource Aware**: 動態調整訓練資源。 |
| **Consistency** | `Hybrid_Model_Consistency_v1.0` | 驗證 System vs Sum(Components) | **Copula Effect**: 考慮組件間的耦合效應，動態計算容許誤差。 |
| **Optimization** | `Chiller_Plant_Optimization_V1.1` | 輸出最佳化建議 | **Blackbox MIP**: 混合整數規劃求解。<br>**Constraint Source**: 定義物理限制 (供 ETL 反向同步)。 |

---

## 3. 關鍵實作細節導讀 (Critical Implementation Details)

### 3.1 為什麼需要 Wizard Technical Blockade?
在之前的設計中，我們發現開發者或使用者可能會為了方便，直接去改 `server/config/features/sites/*.yaml`，導致 Excel (UI端) 與 YAML (系統端) 不同步。
**解決方案**: 
- `src/security/import_guard.py`: 讓 Python 程式碼無法匯入 `yaml` 函式庫，物理上斷絕寫入能力。
- `chattr +i`: 在 Linux 層級鎖死檔案。
這迫使所有變更**必須**回到 Excel 進行，確保 SSOT。

### 3.2 什麼是 PipelineContext 與時間基準？
過去各模組各自呼叫 `datetime.now()`，導致：
- Parser 認為 10:00:00 是現在。
- 到 BatchProcessor 時，時間變成了 10:00:05，結果 10:00:02 的數據被誤判為「過去」，或邊界數據被誤判為「未來」。
**解決方案**: 
- System Integration v1.2 引入 `PipelineContext`。
- 在 Pipeline 啟動瞬間鎖定 `pipeline_timestamp`。
- 所有模組的 `is_future_data()` 檢查都基於這個單一時間點。

### 3.3 設備依賴驗證 (Equipment Dependency) 的反向同步
Optimization 階段定義了「主機開啟時，冷卻水泵必須開啟」。如果歷史數據中有一天主機開了但水泵沒開（可能是感測器壞了），這筆數據若是進入訓練，會讓模型學到錯誤的物理規律。
**解決方案**:
- `ConstraintSyncManager` 在 ETL 階段讀取 Optimization 的規則。
- **Cleaner** 逐行掃描：發現違規 -> 標記 `FLAG_REQUIRES_VIOLATION`。
- **Feature Engineer**: 看到此 Flag -> 將該時段數據視為無效或進行特殊處理，不讓模型學壞。

---

## 4. 建議執行順序 (Phased Execution Plan)

基於模組間的強依賴關係，我們**不能**平行開發所有功能。必須依序建立地基。

### Phase 1: 核心地基 (Foundation)
*   **Step 1.1**: 實作 **Feature Annotation Manager** & **Wizard Blockade**。
    *   *驗收*: Excel 修改能同步到 YAML，且無法直接修改 YAML。
*   **Step 1.2**: 實作 **Constraint Sync Manager** (讀取 Optimization Config)。
*   **Step 1.3**: 建立 **Interface Contract** 的 Error Codes 與 Base Classes。

### Phase 2: 數據管線 (ETL Pipeline)
*   **Step 2.1**: 實作 **System Integration Container** & **Pipeline Context**。
*   **Step 2.2**: 實作 **Parser** (含 UTC 強制)。
*   **Step 2.3**: 實作 **Equipment Validator** (依賴 Step 1.2)。
*   **Step 2.4**: 實作 **Cleaner** (整合 Validator)。
*   **Step 2.5**: 實作 **Batch Processor** (產出 Manifest)。

### Phase 3: 特徵與模型 (Feature & Model)
*   **Step 3.1**: 實作 **Feature Engineer** (讀取 Manifest + Annotation SSOT)。
*   **Step 3.2**: 實作 **Model Training** Pipeline。
*   **Step 3.3**: 實作 **Hybrid Consistency Check**。

### Phase 4: 應用層 (Application)
*   **Step 4.1**: 實作 **Optimization Engine**。
*   **Step 4.2**: API 串接與 UI 呈現。

---

## 5. 解答您的疑問：如何利用這些 PRD？

**給核心開發者 (您) 的操作指南：**

1.  **寫程式前**：先看該模組的 `Input Contract` 和 `Output Contract`。例如寫 Cleaner 時，先看 Interface Contract 定義的 Input 是否符合 Parser 的 Output。
2.  **定義錯誤時**：查閱 `Interface Contract` 的錯誤代碼表 (E000-E999)，不要自己發明錯誤碼。
3.  **處理配置時**：永遠不要 hardcode 設備名稱或物理限制。
    *   問設備角色？ -> `annotation_manager.get_device_role()`
    *   問物理限制？ -> `constraint_manager.get_constraints()`
4.  **提交代碼前**：檢查是否通過了該 PRD 定義的 `Contract Checkpoints` (例如檢查點 #5 Excel/YAML 同步)。

這份報告匯總了所有文件精華，確保您在開發核心功能時，能精準命中需求，避免「做完了才發現架構不對」的風險。
