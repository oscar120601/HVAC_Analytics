# 特徵標註 PRD (v1.1) 審查與優化報告

**審查對象**: `PRD_Feature_Annotation_Specification_V1.1.md`  
**審查重點**: Excel 雙軌制的可行性、Wizard 流程與 SSOT 的衝突風險  
**文件版本**: Review v1.1  
**日期**: 2026-02-13

---

## 1. 總體評價 (General Assessment)

V1.1 版本已顯著改善了 V1.0 的易用性問題，成功引入了 **Excel 介面** 與 **Wizard CLI**，並加入了 **統計驗證 (Distribution Check)**，這對於降低領域專家的操作門檻至關重要。

該文件在架構設計上（Excel → YAML → SSOT）清晰合理。然而，在實作細節上仍有幾個潛在的**技術陷阱**與**流程衝突**需要解決，特別是 Excel 的進階功能限制與雙向同步問題。

---

## 2. 關鍵風險與檢討 (Critical Risks & Findings)

### 2.1 Excel 技術實作風險 (Excel Technical Constraints)

*   **動態下拉選單的脆弱性 (Dynamic Dropdown Fragility)**  
    PRD 提到利用 Excel Data Validation 實現「單位 (C欄)」依賴「物理類型 (B欄)」的動態選單。
    *   **風險**: 在不使用 VBA (巨集) 的情況下，Excel 需依賴 `INDIRECT()` 函數與 Named Ranges。這在使用者進行 **剪貼 (Copy-Paste)** 或 **拖曳 (Drag-Fill)** 操作時非常容易損壞引用，導致驗證失效。
    *   **建議**: 放棄 Excel端的「嚴格動態驗證」，改為：
        1.  Excel 端僅提供「所有單位」的靜態下拉選單（或按類別分群的長選單）。
        2.  **依賴 Python 轉換腳本 (`excel_to_yaml.py`) 進行邏輯檢查** (即 PRD 4.2 節已有的設計)。這能降低 Excel 範本的維護難度。

*   **Excel 版本相容性**  
    *   `schema_version` 目前存在於 Metadata Sheet。建議在 Excel 範本中增加一個隱藏的 `CheckSum` 或 `TemplateVersion` 欄位，確保 Python 腳本能識別並拒絕「舊版 Excel 範本」（例如欄位定義已變更的舊範本）。

### 2.2 流程衝突：Wizard 與 Excel 的競態 (Wizard-Excel Race Condition)

PRD 5.2 描述的 Wizard 流程是：`Wizard -> 更新 YAML`。
同時 PRD 1.2 定義的核心流程是：`Excel -> Python -> YAML`。

*   **風險 (CRITICAL)**: 若使用者先用 Wizard 產生了新的 YAML 設定（例如新增了一台冰機），此時 **Excel 檔案並未同步更新**。
    *   當使用者下次打開舊的 Excel 編輯並匯出時，**Wizard 產生的變更將被覆蓋 (Overwritten)**，導致資料遺失。
*   **建議**: 
    1.  **Wizard 必須操作 Excel**: Wizard 的輸出目標應為更新 `.xlsx` 檔案，而非直接寫入 `.yaml`。
    2.  或者，提供 `yaml_to_excel` 的同步機制（PRD 6.2 已提及），但必須強制規定：「使用 Wizard 後，必須執行 `yaml_to_excel` 更新 Excel，否則禁止下次 Excel 匯入」。
    3.  **最佳解**: 統一流程，Wizard 的作用改為「生成/更新 Excel 草稿」，由使用者打開 Excel 確認後，再執行轉 YAML。這樣確保 Excel 永遠是編輯的源頭。

### 2.3 統計驗證的 False Positive 風險

*   **風險**: `zero_ratio_warning` (零值比例) 對於某些設備（如備用冰機）是常態。若頻繁發出 W403 警告，使用者會習慣性忽略。
*   **建議**: 在 Excel (Sheet 1) 增加一個 `ignore_warnings` 或 `is_backup_device` 欄位，允許使用者顯式聲明「這台設備常態為停機」，從而抑制特定的統計警告。

---

## 3. 優化建議 (Optimization Recommendations)

### 3.1 修正 Wizard 輸出目標

建議將 Wizard 的行為修改為更新 Excel 檔案，保持「Excel = Editor」的原則。

**修正前**:
```bash
python main.py features wizard --site cgmh_ty ...
> ✅ 完成！已更新 config/features/sites/cgmh_ty.yaml
```

**修正後**:
```bash
python main.py features wizard --site cgmh_ty --excel tools/features/cgmh_ty.xlsx
> ✅ 完成！已將新欄位追加至 cgmh_ty.xlsx (Sheet: Columns)
> 請打開 Excel 確認標註，確認後執行 excel_to_yaml.py
```

### 3.2 增強 Excel 範本版本控制

在 `excel_to_yaml.py` 加入範本版本檢查：

```python
EXPECTED_TEMPLATE_VERSION = "1.1"

def validate_excel_template(df_meta):
    ver = df_meta.loc["template_version", 1]
    if ver != EXPECTED_TEMPLATE_VERSION:
        raise ValueError(f"Excel 範本版本過舊 ({ver})，請下載最新版 v{EXPECTED_TEMPLATE_VERSION}")
```

### 3.3 簡化 Group Policy 欄位

在 Excel 的 Group Policies Sheet 中，`Lag 間隔` 與 `Rolling 窗口` 建議改為下拉選單選擇「預設樣板」(如 `Standard_Chiller`, `High_Freq_Sensor`)，而非讓使用者手動輸入數字 `1,4,96`。這樣可以更進一步降低錯誤率，並統一全案場的特徵工程標準。

---

## 4. 結論

V1.1 PRD 方向正確，但在「Excel 與 Wizard 的同步」上存在邏輯漏洞。請務必修正 **Wizard 的輸出目標**，確保 Excel 檔案始終是編輯的唯一入口，避免「雙頭馬車」導致的設定覆蓋問題。

除上述點外，該文件已具備高度的可執行性。
