# PRD 系統總覽與導讀 (PRD System Overview)

本文件旨在為開發者提供與專案 PRD 相關的導航地圖，說明各模組的功能、相依性以及執行順序。

## 1. 系統架構與相依關係圖

整個系統由底層往上層構建，呈現嚴格的單向依賴：

```mermaid
graph TD
    A[Feature Annotation V1.2<br/>(Excel/YAML SSOT)] -->|提供 Schema & 物理限制| C[Cleaner V2.2]
    Z[Raw Files] -->|解析| B[Parser V2.1]
    B -->|UTC DataFrame| C
    C -->|Cleaned DataFrame| D[Batch Processor V1.3]
    D -->|Manifest + Parquet| E[Feature Engineer V1.3]
    A -->|提供 device_role & 規則| E
    E -->|Feature Matrix| F[Model Training V1.2]
    F <-->|一致性驗證| G[Hybrid Consistency V1.0]
    F -->|Model Registry| H[Optimization Engine V1.1]
    A -->|提供限制條件| H
    
    style A fill:#f9f,stroke:#333,stroke-width:4px
    style B fill:#eef,stroke:#333,stroke-width:2px
    style C fill:#bbf,stroke:#333,stroke-width:2px
    style D fill:#ddf,stroke:#333,stroke-width:2px
    style E fill:#bfb,stroke:#333,stroke-width:2px
    style F fill:#fbb,stroke:#333,stroke-width:2px
    style G fill:#fdd,stroke:#333,stroke-width:2px
    style H fill:#eef,stroke:#333,stroke-width:2px
```

## 2. 各 PRD 功能詳解

### 2.1 [基礎設施] Feature Annotation Specification (V1.2)
*   **功能**: 作為整個系統的 **Single Source of Truth (SSOT)**。定義所有感測器點位、物理類型、單位、上下限範圍以及設備角色 (Primary/Backup)。
*   **相依性**: 無 (這是最底層)。
*   **關鍵產出**: `config/features/sites/*.yaml` (由 Excel 生成)。

### 2.2 [介面規範] Interface Contract (V1.0)
*   **功能**: 定義模組間的溝通語言與錯誤處理標準。包含錯誤代碼表 (E000-E999)、資料交換格式 (Checkpoint)、以及版本相容性矩陣。

### 2.3 [資料前處理] 
#### Parser (V2.1)
*   **功能**: 處理「髒」的原始檔案。負責編碼偵測 (BOM/Big5)、強制時區轉 UTC、與標頭正規化。
*   **相依性**: `Interface Contract` (檢查點 #1)。
*   **關鍵產出**: 標準化 DataFrame (UTC, UTF-8)。

#### Cleaner (V2.2)
*   **功能**: 業務邏輯清洗。處理時間對齊、異常值過濾 (基於 Annotation)、冷凍數據檢測。
*   **相依性**: `Parser` (輸入), `Feature Annotation` (規則)。
*   **關鍵產出**: Cleaned DataFrame (無 `device_role` 欄位)。

#### Batch Processor (V1.3)
*   **功能**: ETL 流程編排與落地。生成 `Manifest` (含 Annotation 稽核軌跡) 與 `Parquet` 檔案。確保資料與 Metadata 的完整傳遞，但不處理業務邏輯。
*   **相依性**: `Cleaner` (輸入)。
*   **關鍵產出**: `manifest.json` + `data.parquet`。

### 2.4 [特徵工程] Feature Engineer (V1.3)
*   **功能**: 讀取 Manifest，結合 **Feature Annotation** (直接讀取 YAML SSOT) 來產生模型特徵。處理 Lag、Rolling Window，並根據設備角色調整策略。
*   **相依性**: `Batch Processor` (輸入), `Feature Annotation` (設備角色)。
*   **關鍵產出**: Feature Matrix。

### 2.5 [模型訓練與驗證]
#### Model Training (V1.2)
*   **功能**: 訓練能耗預測模型 (System & Component Level)。
*   **關鍵產出**: `model_registry_index.json` + 模型檔案。

#### Hybrid Model Consistency (V1.0)
*   **功能**: 驗證 System Model 與 Component Models 加總的一致性。處理耦合效應 (Copula Effect) 與動態容差。
*   **相依性**: 被 `Model Training` (驗證階段) 與 `Optimization` (執行階段) 呼叫。

### 2.6 [最佳化] Optimization Engine (V1.1)
*   **功能**: 離線建議。基於模型預測與物理限制，尋找最佳設備參數。
*   **相依性**: `Model Training` (載入模型), `Feature Annotation` (物理限制)。

## 3. 開發建議順序 (更新版)

1.  **Feature Annotation Manager**: (最優先) 建立地基。
2.  **Parser**: 處理原始資料的入口。
3.  **Cleaner**: 實作資料清洗邏輯。
4.  **Batch Processor**: 串接資料流與落地。
5.  **Feature Engineer**: 產生特徵。
6.  **Hybrid Consistency**: 建立驗證標準。
7.  **Model Training**: 訓練模型。
8.  **Optimization Engine**: 實現業務價值。
