# 特徵標註 PRD (v1.2) 審查與最終確認報告

**審查對象**: `PRD_Feature_Annotation_Specification_V1.2.md`  
**審查重點**: Excel 編輯流程的封閉性、版本控制機制的穩健性  
**文件版本**: Final Review v1.2  
**日期**: 2026-02-13

---

## 1. 總體評價 (General Assessment)

**V1.2 版本是非常成熟且可執行的狀態。**

該版本已完美解決了前次審查中提出的「Wizard 與 Excel 競態條件」問題，並策略性地放棄了脆弱的 Excel 動態驗證，轉而依賴穩健的 Python 轉換層驗證。整體設計體現了「簡單前端 (Excel) + 嚴謹後端 (Python Check)」的設計哲學，極大降低了人為錯誤的機率。

特別是在版本控制上，引入了 `schema_hash` 與 `template_version`，這解決了長期維護中最棘手的「範本過期」與「手動篡改 YAML」問題。

---

## 2. 優點摘要 (Strengths)

1.  **解決競態條件 (Critical Fix)**: 
    *   明確定義 Wizard **只更新 Excel**，YAML 只能透過 `excel_to_yaml.py` 生成。這建立了唯一的資料流向：`Wizard -> Excel -> YAML -> Git`，從根本上消除了同步衝突。
2.  **務實的 Excel 設計**: 
    *   放棄 `INDIRECT()` 動態下拉選單是一個非常明智的決定。這避免了因複製貼上導致的 Excel 參照錯誤，將複雜邏輯移至 Python 層處理更易於維護與擴展。
3.  **設備角色 (Device Role)**: 
    *   新增 `device_role: backup/seasonal` 解決了因設備停機導致的 "False Positive" 警告，提升了統計驗證的實用性，避免「狼來了」效應。
4.  **完整的版本防護**: 
    *   透過 Hidden Sheet 儲存 `template_version` 與 `schema_hash`，配合 CI/CD 的同步檢查，形成了一個閉環的防篡改機制。

---

## 3. 最後的微調建議 (Final Recommendations)

雖然架構已無大礙，但有幾個**實作細節**建議在開發階段注意：

### 3.1 關於 `yaml_to_excel.py` 的安全性 (Safety Guard)

PRD 7. 允許使用 `yaml_to_excel` 進行初始化。
*   **建議**: 為了防止誤覆蓋，該腳本應預設**拒絕覆蓋已存在的 Excel 檔案**。
*   **實作**: 必須加上 `--force` 參數才能覆蓋現有檔案，並在執行前顯示警告：「警告：這將覆蓋現有 Excel 中的公式與註解，確定執行？」

### 3.2 針對 `ignore_warnings` 的語法

PRD 3.1 Sheet 1 定義了 H 欄為 `ignore_warnings`。
*   **建議**: Excel 中建議支援更友善的輸入方式。例如，如果使用者輸入「全部」或「ALL」，程式應能理解為忽略所有警告，而不僅限於代碼 `W401,W403`。這對現場人員更直覺。

### 3.3 關於 Log 記錄 (Audit Trail)

PRD 6.2 Wizard 流程。
*   **建議**: 每次 Wizard 更新 Excel 時，除了更新 Sheet 內容，建議在一個新的 Sheet (如 `History`) 寫入一行 Log (Timestamp, User, Action, Affected Columns)。這對於多人協作的案場（如長庚醫院有數十台冰機）非常有幫助，能追溯「是誰加了這個欄位」。

---

## 4. 執行下一步 (Next Steps)

此 PRD 已無 Blockers，建議**立即進入開發階段**。

建議的開發順序：
1.  **Tools**: 優先實作 `data_model.py` (Pydantic) 與 `excel_to_yaml.py` (核心轉換邏輯)。
2.  **Template**: 製作 `Feature_Template_v1.2.xlsx` 並鎖定 Hidden Sheet。
3.  **Wizard**: 開發 CLI，確保它能正確讀寫 Excel (使用 `openpyxl` 需注意保留原有樣式)。
4.  **CI/CD**: 配置 GitHub Actions 的同步檢查。

---

**結論**: 可以 Approvel (簽核通過)。
