# System Integration PRD (v1.1) 審查報告

**審查對象**: `docs/System Integration/PRD_System_Integration_v1.1.md`  
**審查基準**: `Feature Annotation Specification v1.2` (Excel為核心 SSOT)  
**文件版本**: System Integration v1.1 Review  
**日期**: 2026-02-13

---

## 1. 總體評價 (General Assessment)

該份 System Integration PRD (v1.1) **高度符合** Feature Annotation v1.2 的核心精神。

文件成功將 Feature Annotation 定義為 Pipeline 的上游依賴，並正確實作了：
1.  **單向資料流**: 明確定義了 Excel → YAML → Pipeline 的流向。
2.  **依賴注入**: 透過 `ETLContainer` 將 `FeatureAnnotationManager` 注入給 Cleaner 與 Feature Engineer，解決了「模組如何取得特徵定義」的問題。
3.  **同步防護 (Safety Guard)**: 在 Pipeline 入口處 (CLI) 與執行層 (Container) 都加入了 E406 同步檢查，這是防止運維災難的關鍵設計。

然而，在 **Cleaner 的整合細節** 與 **Wizard 的職責邊界** 上，仍有細微的邏輯漏洞需要修正。

---

## 2. 詳細審查發現 (Detailed Findings)

### 2.1 ✅ 正確的設計 (Good Practices)

*   **配置結構 (Config Models)**: 
    *   `FeatureMetadata` 正確新增了 `device_role` 與 `ignore_warnings`。
    *   `CleanerConfig` 與 `FeatureEngineeringConfig` 正確新增了對應的開關 (`respect_device_role`)。
*   **載入器 (ConfigLoader)**:
    *   `load_feature_annotation` 與 `validate_annotation_sync` 的邏輯正確，特別是 Checksum 的比對機制。
*   **CLI 架構**:
    *   將 `features wizard` 獨立為子命令，且明確標示「僅更新 Excel」，這符合 v1.2 的核心約束。

### 2.2 ⚠️ 潛在風險與修正建議 (Risks & Recommendations)

#### 1. Cleaner 的職責邊界模糊 (Cleaner Responsibility)

在 `PRD 3.1 ETLContainer.get_cleaner()` 中提到：
> Cleaner v2.2+ 會: 2. 將 device_role 寫入 metadata

**風險**: Cleaner 的職責應專注於「資料清洗 (Cleaning)」。將 `device_role` 寫入 metadata 雖然可行，但這其實是「特徵增強 (Enrichment)」的一環。
**建議**: 
*   Cleaner 僅需負責「讀取 `ignore_warnings`」來決定是否過濾掉特定的品質標記 (Quality Flags)。
*   `device_role` 的主要消費者是 **Feature Engineer** (用於抑制統計警告) 與 **Batch Processor** (用於分群)。不需要在 Cleaner 階段就寫入 dataframe metadata，這會增加耦合。建議改為由 `AnnotationManager` 直接提供給需要的模組即可。

#### 2. Wizard 的 `guess_physical_type` 邏輯缺漏

在 `PRD 6.2 Wizard` 範例代碼中：
```python
suggestion = guess_physical_type(col, stats)
```
**風險**: 該函數未在 PRD 中定義。
**建議**: 應補充說明 `guess_physical_type` 的判斷邏輯（例如：欄位名稱包含 `temp` -> `temperature`），或是明確標示這是一個待實作的 utility function。

#### 3. 繼承架構的遺漏 (Inheritance Gap)

Feature Annotation v1.2 提到了 `inherit: base` 的概念，但在 System Integration PRD 的 `load_feature_annotation` 中，似乎只載入了 `site_id.yaml`，**沒有看到合併 `base.yaml` 的邏輯**。
**風險**: 如果 `site_id.yaml` 只包含差異 (Delta)，那載入的設定將不完整。
**建議**: `FeatureAnnotationManager._load()` 必須實作「遞迴載入與合併 (Recursive Load & Merge)」邏輯：
1. 讀取 `site.yaml`，檢查 `inherit` 欄位。
2. 若有 `inherit`，載入父 YAML。
3. 將子設定覆蓋 (Override) 父設定。

### 2.3 ❌ 需要修正的錯誤 (Errors to Fix)

#### 1. Device Role 的預設值衝突

*   在 `Config Models` (2.1) 中，`CleanerConfig.default_device_role = "primary"`。
*   在 `Feature Annotation v1.2` Excel 中，`backup` 是明確標示的，未標示則為 `primary`。
*   **衝突**: 系統不應有全域的 `default_device_role` 設定。每個欄位的 role 應完全取決於 Annotation。若 Annotation 未定義該欄位，則該欄位根本不應參與 Pipeline (除非是 raw data)。
*   **修正**: 移除 `CleanerConfig.default_device_role`，避免隱性錯誤。

---

## 3. 結論與行動 (Conclusion)

這份 System Integration PRD 架構穩健，但在「繼承合併」與「設定預設值」上有小瑕疵。

**行動建議**:
1.  **修正 `FeatureAnnotationManager`**: 必須明文規定實作 YAML Merge (Base + Site) 的邏輯，否則繼承功能將失效。
2.  **移除 Cleaner 的 Default Role**: 讓 Annotation 成為真正的 SSOT，不要在 Config 中藏預設值。

除此之外，該文件可作為開發依據。
