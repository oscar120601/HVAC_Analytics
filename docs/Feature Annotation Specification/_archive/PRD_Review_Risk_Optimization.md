# 特徵標註 PRD (v1.0) 風險評估與優化建議報告

**評估對象**: `PRD_Feature_Annotation_Specification_V1.0.md`  
**評估重點**: 人工標註作業流程 (Manual Annotation Workflow)  
**文件版本**: Review v1.0  
**日期**: 2026-02-13

---

## 1. 執行摘要 (Executive Summary)

本 PRD 確立了「人機分離」的核心架構，將特徵定義權下放至領域專家（空調技師），設計理念先進且符合 MLOps 最佳實踐。然而，針對**人工介入**環節，目前的 YAML 方案對非技術人員存在顯著的**操作門檻**與**人為錯誤風險**。

雖然系統層面有完善的 `Validator` 與 `Schema` 防護，但「防呆」不等於「好用」。若標註過程過於繁瑣或易錯，將導致領域專家抗拒使用，最終回歸到工程師代勞，違背「非工程師可維護」的初衷。

建議引入**中間層工具 (Excel/GUI)** 與 **交互式驗證流程** 來對沖這些風險。

---

## 2. 潛在風險評估 (Risk Assessment)

### 2.1 人為操作風險 (Human Factors) - **CRITICAL**

| 風險點 | 說明 | 影響 |
|:---|:---|:---|
| **YAML 語法門檻** | 空調技師/設備工程師通常不熟悉 YAML 縮排、冒號與列表格式。 | 導致大量 `SCHEMA_VALIDATION_FAILED` (E400)，挫折感高，效率低落。 |
| **正則表達式 (Regex) 困難** | `Group Policy` 依賴 Regex (`^chiller_\d+_.*$`) 進行自動匹配。 | 領域專家無法編寫或維護 Regex，導致 Group Policy 形同虛設，退化為逐行設定。 |
| **物理意義誤植** | 誤將「壓力 (Bar)」標註為「溫度 (C)」。 | Cleaner 的 `valid_range` 檢查失效（例如壓力的 0-10 Bar 在溫度 -40~100 範圍內是合法的），導致髒數據流入模型。 |
| **版本號混亂** | 人工需手動維護 `schema_version` 與檔案版本。 | 容易發生 Copy-Paste 錯誤，導致版本號與內容不符。 |

### 2.2 流程整合風險 (Process Integration) - **HIGH**

| 風險點 | 說明 | 影響 |
|:---|:---|:---|
| **CSV 與 YAML 不同步** | 現場 IoT Gateway 變更點位名稱，但 CSV 欄位變更後，YAML 未及時更新。 | 嚴格模式下觸發 `E402_UNANNOTATED_COLUMN` 導致 Pipeline 中斷；非嚴格模式下導致資料遺失。 |
| **繼承邏輯黑盒** | 多層繼承 (`Site` -> `Base` -> `Physics`) 的最終結果對人類不可見。 | 使用者在子檔案修改屬性時，不確定是否正確覆蓋了父檔案，需依賴 CLI `diff` 工具才能確認。 |
| **缺乏即時反饋** | 目前依賴 CLI (`python main.py features validate`) 進行檢查。 | 標註過程中無法即時得知錯誤（如 Excel 的資料驗證），需等到執行 CLI 才知道失敗。 |

### 2.3 技術實作風險 (Technical Implementation) - **MEDIUM**

| 風險點 | 說明 | 影響 |
|:---|:---|:---|
| **Lag/Rolling 盲點** | 即便有 E405 防護 (Target Leakage)，但對於非 Target 的欄位，使用者可能不理解 `lag_intervals` 的統計意義。 | 產生無意義的特徵（如對「機型編號」做 Rolling Mean），造成運算資源浪費。 |
| **檔案命名規範** | 依賴檔名 (`cgmh_ty.yaml`) 作為 Site ID。 | 若檔名更改但內容未變，或大小寫不一致，可能導致 ConfigLoader 載入失敗。 |

---

## 3. 優化建議與解決方案 (Optimization Strategy)

針對上述風險，建議從**工具鏈 (Tooling)** 與 **流程 (Workflow)** 兩個維度進行優化。

### 3.1 工具鏈優化：引入 Excel 作為中間層 (Excel-as-Interface)

YAML 適合機器讀取與版本控制，但不適合人類編輯。建議開發 **CSV/Excel 轉換器**。

*   **方案**: 設計一個標準化的 Excel 範本 (`Feature_Definition_Template.xlsx`)。
    *   **Sheet 1 (Columns)**: 表格化列出所有欄位，下拉式選單選擇 `Physical Type`。
    *   **Sheet 2 (Physical Types)**: 唯讀參考，列出所有可用類型與單位。
    *   **Sheet 3 (Group Policy)**: 簡單的規則設定（非 Regex，改用「包含字串」或「前綴」）。
*   **優勢**: 
    1. 領域專家熟悉 Excel。
    2. 可利用 Excel 的「資料驗證 (Data Validation)」做第一層防呆（如下拉選單）。
    3. 透過 Python Script (`excel_to_yaml.py`) 自動轉換為規範的 YAML，解決縮排問題。

### 3.2 驗證流程優化：交互式 CLI (Interactive CLI)

現有的 `init` 指令僅能產生草稿，建議增強為 **Wizard 模式**。

*   **新增指令**: `python main.py features wizard --csv data.csv`
*   **功能**:
    1. 讀取 CSV，逐一列出未定義欄位。
    2. 顯示：「發現新欄位 `chiller_1_kwh`，系統推測為 `Energy`，是否確認？(Y/n/Edit)」
    3. 自動更新 YAML 檔案，無需人工開啟編輯器。

### 3.3 物理意義驗證：數據分佈檢查 (Distribution Check)

在 `validate_against_dataframe` 中加入**統計驗證**，而非僅檢查型別。

*   **邏輯**: 
    *   若標註為 `Temperature` (範圍 -40~100)，但實際數據 `mean=400`，則發出 **Warning (W40x)**。
    *   這能抓出「標註錯誤」或「單位錯誤」（如攝氏誤為華氏，或壓力誤為溫度）。

### 3.4 繼承視覺化 (Inheritance Visualization)

*   **新增指令**: `python main.py features inspect cgmh_ty --column chiller_1_temp`
*   **輸出**:
    ```text
    Column: chiller_1_temp
    Final Config:
      - physical_type: temperature (from BASE)
      - enable_lag: false (OVERRIDDEN by SITE)
      - unit: C (from PHYSICS)
    ```
*   這能幫助使用者理解繼承的最終結果。

---

## 4. 具體修訂建議 (Specific Revisions to PRD)

建議在 PRD v1.1 中加入以下章節或修改：

1.  **修改 3.1 頂層結構**:
    *   增加 `meta` 欄位，紀錄 `editor` (編輯者) 與 `last_updated`，便於追溯責任。
2.  **增強 6. CLI 工具規格**:
    *   將 `init` 升級為 `wizard` 或支援 Excel 導入 (`--from-excel`)。
3.  **新增 4.4 統計分佈驗證**:
    *   定義 Warning 級別的錯誤，允許 Pipeline 繼續執行但產出警告報告。
4.  **Group Policy 簡化**:
    *   除了 Regex `match_pattern`，增加 `starts_with`, `ends_with`, `contains` 等簡單字串匹配規則，降低門檻。

---

## 5. 結論

目前的 PRD 在架構設計上非常嚴謹（SSOT, Pydantic, Composition），是高品質的工程規範。
**唯一的缺口在於「User Interface」**。

若能補足 **Excel 轉譯工具** 或 **交互式 CLI**，將能大幅降低推動阻力，確保該系統真正能被空調技師所用，達成「人機分離」的最終目標。
