# Project Structure & Optimization Review Report v1.0
**日期:** 2026-02-13
**審閱對象:** HVAC-1 Project Structure vs Updated PRDs (v1.2/v2.1)

---

## 1. 執行總結 (Executive Summary)

經過與最新 PRD 文檔（特別是 `PRD_System_Integration_v1.2.md` 與 `PRD_INTERFACE_CONTRACT_v1.0.md`）的比對，專案目前處於 **「架構轉型中」 (Transition Phase)** 的狀態。

*   **✅ 已符合項目**:
    *   `src/` 目錄結構已建立（區分 `etl`, `optimization`, `models`, `config`）。
    *   `interface.py` 與 `schemas.py` 已存在，符合重構建議書的 Facade 設計。
    *   文檔庫 (`docs/`) 已全面更新並具備 HTML 版本，舊檔已歸檔至 `_archive`。

*   **❌ 關鍵缺失 (Critical Gaps)**:
    *   **系統整合核心缺失**: `PRD_System_Integration_v1.2.md` 定義的 **DI Container (`container.py`)**、**Pipeline Context (`context.py`)** 與 **Feature Annotation Manager** 尚未實作。
    *   **ETL 模組缺漏**: `src/etl/` 缺少 `feature_engineer.py`，且現有的 `parser.py`/`cleaner.py` 尚未升級至支援新的 Error Code (E1xx/E2xx) 與時間基準機制。
    *   **配置管理**: `src/utils/config_loader.py` 缺失，且 `config/` 目錄尚未建立 `sites/` 子目錄來存放 YAML SSOT。

---

## 2. 詳細差異分析

### 2.1 程式碼結構 vs PRD System Integration v1.2

| 模組 | 預期檔案 (PRD v1.2) | 實際狀態 | 嚴重性 | 說明 |
|:---|:---|:---|:---:|:---|
| **Core** | `src/container.py` | 🔴 **Missing** | High | 缺乏依賴注入容器，無法管控初始化順序 |
| **Core** | `src/context.py` | 🔴 **Missing** | High | 缺乏全域時間基準 `PipelineContext` |
| **Config** | `src/utils/config_loader.py` | 🔴 **Missing** | High | 無法載入新的 YAML 配置與 Annotation |
| **Features** | `src/features/annotation_manager.py` | 🔴 **Missing** | High | 缺乏 Excel/YAML 同步與繼承邏輯 |
| **ETL** | `src/etl/feature_engineer.py` | 🔴 **Missing** | High | 特徵工程模組未整合至 ETL 流程 |
| **Config** | `config/features/sites/*.yaml` | 🔴 **Missing** | Med | 尚未從 Excel 生成 YAML SSOT |

### 2.2 重構建議書 (`review_restructuring_proposal.md`) 審閱

您的同事提出的重構建議書 **方向正確**，但對照最新的 PRD v1.2 需求，有以下優化建議：

1.  **Interface 層級不足**: 建議書僅提到 `interface.py`，但在 v1.2 設計中，**`ETLContainer`** 才是真正的系統入口與組裝者。`interface.py` 應作為對外部（如 API 或 CLI）的 Facade，內部呼叫 `ETLContainer`。
2.  **忽略了時間一致性**: 建議書未提及「時間基準 (Temporal Baseline)」問題，這是 v1.2 解決 Data Leakage 的核心機制 (`PipelineContext`)。
3.  **配置管理過於簡化**: 建議書建議將配置改為 YAML，但未考慮到 HVAC 案場的「特徵標註 (Feature Annotation)」複雜度（Excel -> YAML 機制）。

---

## 3. 文檔庫狀態 (Documentation Status)

所有 PRD 文檔已完成更新與歸檔：

*   **最新版本**: 存放於各子目錄根目錄 (如 `docs/parser/PRD_Parser_V2.1.md`)。
*   **HTML 版本**: 已全數生成，方便非技術人員閱讀。
*   **舊版歸檔**: 所有 v1.0/v1.1 或 Review 報告已移至對應的 `_archive` 子目錄。

---

## 4. 下一步行動建議 (Action Plan)

建議立即啟動 **Phase 2: Code Implementation**，按以下順序補齊缺失：

1.  **基礎建設 (Infrastructure)**:
    *   實作 `src/context.py` (PipelineContext)
    *   實作 `src/utils/config_loader.py`
    *   實作 `src/container.py` (ETLContainer - 這是系統的心臟)

2.  **特徵管理 (Feature Management)**:
    *   建立 `src/features/` 目錄
    *   實作 `annotation_manager.py`
    *   執行 `excel_to_yaml` 轉換，產出首版 `config/features/sites/*.yaml`

3.  **ETL 模組升級**:
    *   重構 `src/etl/parser.py` (對接 E1xx 錯誤碼)
    *   重構 `src/etl/cleaner.py` (對接 E2xx 錯誤碼 & Context)
    *   新增 `src/etl/feature_engineer.py`

此順序確保了「依賴先行」(Dependencies First)，避免後續整合時發生重寫。
