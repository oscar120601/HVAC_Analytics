# PRD v1.1: Web 應用層架構與 API 介面規範 (Web Application Architecture & API Interface)

**文件版本:** v1.1 (Interface Contract Alignment & Full Pipeline Coverage)  
**日期:** 2026-02-23  
**負責人:** Oscar Chang  
**範圍:** Web 前端 (Frontend)、Web 後端 (Backend)、非同步任務排程、與底層 Python AI 引擎 (ETL & ML & Optimization) 的銜接及部署規範  
**相依文件:** 
- PRD_System_Integration_v1.2.md
- PRD_Interface_Contract_v1.1.md
- PRD_Feature_Annotation_Specification_V1.3.md
- PRD_Model_Training_v1.3.md
- PRD_Chiller_Plant_Optimization_V1.2.md
- PRD_Equipment_Dependency_Validation_v1.0.md
- PRD_Hybrid_Model_Consistency_v1.0.md

**修訂紀錄 (v1.0 → v1.1):**
- 完整對齊 Interface Contract v1.1 的 11 層錯誤代碼（E000-E999）
- 新增 Model Training、Equipment Validation、Hybrid Consistency API 群組
- 新增 Temporal Baseline 在 Web 層的傳遞規範
- 擴充 Dashboard JSON Schema（Quality Flags、Equipment Validation 摘要）
- 更新 App Database 職責（Model Registry、Audit 日誌）

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標
本規範專為 **Web 前端與後端工程師** 提供清晰的銜接指引，定義如何將現有高複雜度的 Python ETL / ML / Optimization 底層元件，封裝為穩定、非同步且可視化的 Web 軟體服務。
1. **前後端解耦**: Web 後端作為 Gateway，集中處理 Authentication (驗證)、RBAC (權限)，再轉發指令給底層 Python Worker。
2. **非同步任務處理 (Async Task)**: 數據解析 (Parser)、資料清洗 (Cleaner)、模型訓練 (Training)、最佳化推論 (Optimization) 均為耗時作業，需藉由任務佇列避免阻擋 HTTP Request。
3. **狀態即時反饋**: 處理底層產生的 **E000-E999 錯誤代碼**與 **W4xx 系列警告**，將其轉換為前端可讀的 HTTP 狀態碼與提示訊息。
4. **圖表結構統一**: 定義供前端繪製 Dashboard 使用的標準 JSON Schema（含 Quality Flags 摘要、Equipment Validation 統計）。
5. **時間基準一致性**: 將底層的 `pipeline_origin_timestamp`（Temporal Baseline）傳遞至 Web 層，確保前端展示與底層邏輯時間一致。

### 1.2 系統架構邊界 (System Context)

```mermaid
graph TD
    subgraph "Web Frontend (React / Vue)"
        UI_Dash[Dashboard & 報表]
        UI_Task[處理進度監控]
        UI_Conf[Feature Wizard Web UI]
        UI_Train[模型訓練管理]
        UI_Quality[數據品質報表]
    end

    subgraph "Web Backend (Node.js / Go / Java)"
        API_GW[API Gateway & Router]
        Auth[認證與權限管理]
        Task_Sched[任務排程器 cron/JobManager]
        Health[Health Check & Version Matrix]
    end

    subgraph "Middleware / Infrastructure"
        DB[(App DB / PostgreSQL)<br>使用者狀態, Task日誌,<br>Model Registry, Audit]
        Queue[[Message Queue / Redis/RabbitMQ]<br>Task ID & 狀態]
        WebSocket((WebSocket/SSE Server))
    end

    subgraph "Python AI/ETL Engine (底層運算)"
        Py_Worker[Python Worker Process]
        ETL_Pipe[Parser → Cleaner → FE]
        ML_Model[Training & Optimization]
        EqValid[Equipment Validator]
        HybridCheck[Hybrid Consistency Checker]
        FileSystem[(Parquet / YAML SSOT)]
    end

    UI_Dash -- "REST API (JSON)" --> API_GW
    UI_Conf -- "設定變更" --> API_GW
    UI_Task -- "WebSocket: 接收進度" --> WebSocket
    UI_Train -- "Training 控制" --> API_GW
    UI_Quality -- "品質報表" --> API_GW

    API_GW -- "管理權限" --> Auth
    API_GW -- "CRUD 應用狀態" --> DB
    API_GW -- "發佈長效任務" --> Queue
    API_GW -- "健康檢查" --> Health
    
    Queue -- "派發" --> Py_Worker
    Py_Worker -- "啟動" --> ETL_Pipe
    Py_Worker -- "訓練/優化" --> ML_Model
    Py_Worker -- "設備驗證" --> EqValid
    Py_Worker -- "混合模型一致性" --> HybridCheck
    Py_Worker -- "讀寫 Data" --> FileSystem
    
    Py_Worker -- "回報 0~100% 進度 & Error (E000-E999)" --> Queue
    Queue -- "狀態更新" --> WebSocket
```

---

## 2. API 端點設計規範 (RESTful API Contracts)

Web Backend 需對 Frontend 提供以下核心 REST API 分群：

### 2.1 資料前處理與 ETL 觸發 (ETL Pipeline)
*   **`POST /api/v1/pipeline/batch`**
    *   **用途**: 上傳新的 CSV，或指定伺服器特定目錄的資料，啟動 Batch ETL 流程（Parser → Cleaner → BatchProcessor → FeatureEngineer）。
    *   **Response**: HTTP 202 Accepted, 返回 `{ "task_id": "uuid-12345" }`
*   **`GET /api/v1/pipeline/tasks/:task_id`**
    *   **用途**: 查詢 ETL 任務狀態（`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`）。
    *   **Response**: 回傳進度百分比、Warning 列表（W401-W407）、**pipeline_origin_timestamp** 以及 Equipment Validation 摘要。
*   **`GET /api/v1/pipeline/temporal-context`**
    *   **用途**: 查詢當前或最近一次 Pipeline 執行的時間基準（Temporal Baseline），供前端展示「資料截止時間」與「處理基準時間」。

### 2.1.1 CSV 解析與格式選擇 (Parser V2.2)
*取代原本單一 Parser，改用模組化策略模式，支援多種 CSV 格式。*

**Parser 策略管理**
*   **`GET /api/v1/parser/strategies`**
    *   **用途**: 取得所有可用的 CSV Parser 類型列表。
    *   **Response**: 
        ```json
        {
          "strategies": [
            {
              "id": "generic",
              "name": "通用 CSV 解析器",
              "description": "適用於標準 Date/Time 格式的通用 CSV 檔案",
              "supported_patterns": ["*.csv"]
            },
            {
              "id": "siemens_scheduler",
              "name": "Siemens Scheduler Report",
              "description": "適用於 Siemens Scheduler 匯出格式 (CGMH-TY, Farglory O3, KMUH)",
              "supported_patterns": ["TI_ANDY_SCHEDULER_USE_REPORT_*.csv", "adv_*.csv", "TR_KH_*.csv"]
            }
          ]
        }
        ```

**CSV 解析與預覽**
*   **`POST /api/v1/pipeline/parse-preview`**
    *   **用途**: 使用指定的 Parser 類型解析 CSV，回傳預覽結果（不執行完整 ETL）。
    *   **Payload**: 
        ```json
        {
          "temp_file_id": "temp_abc123",
          "parser_type": "siemens_scheduler",
          "site_id": "cgmh_ty"
        }
        ```
    *   **Response**:
        ```json
        {
          "status": "success",
          "parser_used": "siemens_scheduler",
          "metadata": {
            "encoding": "utf-8",
            "header_line": 127,
            "total_points": 122,
            "row_count": 672,
            "timestamp_range": {
              "min": "2015-12-13T00:00:00+00:00",
              "max": "2015-12-19T23:45:00+00:00"
            }
          },
          "point_mapping": {
            "Point_1": {"name": "AHWP-3.KWH", "normalized_name": "ahwp_3_kwh"},
            "Point_2": {"name": "AHWP-4.KWH", "normalized_name": "ahwp_4_kwh"}
          },
          "columns": ["timestamp", "ahwp_3_kwh", "ahwp_4_kwh", "..."],
          "sample_rows": [
            {"timestamp": "2015-12-13T00:00:00+00:00", "ahwp_3_kwh": 127316}
          ]
        }
        ```

**Wizard Excel 生成**
*   **`POST /api/v1/wizard/generate-excel`**
    *   **用途**: 根據 CSV 解析結果生成 Feature Annotation Excel 範本。
    *   **Payload**:
        ```json
        {
          "temp_file_id": "temp_abc123",
          "parser_type": "siemens_scheduler",
          "site_id": "cgmh_ty",
          "template_version": "1.3"
        }
        ```
    *   **Response**: HTTP 202 Accepted
        ```json
        {
          "task_id": "wizard_task_456",
          "status": "processing",
          "download_url": "/api/v1/wizard/download/wizard_task_456",
          "preview_data": {
            "total_columns": 124,
            "new_columns": 122,
            "point_mapping_summary": "122 points mapped"
          }
        }
        ```

**UI 操作流程**:
```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  上傳 CSV   │ →  │ 選擇 Parser 類型 │ →  │ 預覽解析結果    │
└─────────────┘    └─────────────────┘    └─────────────────┘
                                                  ↓
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 執行 ETL    │ ←  │ 轉換為 YAML     │ ←  │ 下載/編輯 Excel │
│ Pipeline    │    │ (excel_to_yaml) │    │ 標註範本        │
└─────────────┘    └─────────────────┘    └─────────────────┘
```

### 2.2 設備與特徵設定 (Feature Annotation v1.3)
*取代原本文本化的 Wizard CLI，改用直覺的網頁操作。*

**2.2.1 Column Annotations 管理**
*   **`GET /api/v1/facilities/:site_id/equipment/annotations`**
    *   **用途**: 讀取 YAML (SSOT) 並回傳設備欄位標註清單（physical_type, unit, device_role 等）。
*   **`PUT /api/v1/facilities/:site_id/equipment/annotations`**
    *   **用途**: 前端更新標註後，Web Backend 寫入更新至後端，由系統安全地執行 `excel_to_yaml.py`。
    *   **合規要求**: 須遵循 E501 防護，不可繞過 SSOT 制定的寫入驗證機制。

**2.2.2 Group Policies 管理**
*   **`GET /api/v1/facilities/:site_id/group-policies`**
    *   **用途**: 取得案場的群組策略清單（prefix/suffix 匹配、物理類型、Lag 設定模板）。
*   **`PUT /api/v1/facilities/:site_id/group-policies`**
    *   **用途**: 更新群組策略，透過 `excel_to_yaml.py` 同步至 YAML SSOT。

**2.2.3 Equipment Constraints 管理**
*   **`GET /api/v1/facilities/:site_id/equipment-constraints`**
    *   **用途**: 讀取設備邏輯限制條件（requires, mutex, sequence, min_runtime, min_downtime）。
*   **`PUT /api/v1/facilities/:site_id/equipment-constraints`**
    *   **用途**: 更新設備限制條件。此操作同時影響 Cleaner 預檢與 Optimization 約束。

**2.2.4 Excel 上傳與同步**
*   **`POST /api/v1/facilities/:site_id/annotation/upload-excel`**
    *   **用途**: 上傳新的 Feature Template Excel 檔案，觸發 `excel_to_yaml.py` 轉換流程。
    *   **Response**: HTTP 202 Accepted, 返回同步任務狀態。

### 2.3 模型訓練管理 (Model Training v1.3)
*   **`POST /api/v1/training/start`**
    *   **用途**: 啟動模型訓練任務。
    *   **Payload**: 指定訓練模式（`system_only`, `component_only`, `hybrid`）、目標變數、超參數配置、資源限制。
    *   **Response**: HTTP 202, 返回 `{ "task_id": "task_train_789" }`
*   **`GET /api/v1/training/tasks/:task_id`**
    *   **用途**: 查詢訓練進度，包含 Checkpoint 資訊、交叉驗證進度、資源使用量。
*   **`GET /api/v1/training/models`**
    *   **用途**: 列出已註冊的模型（讀取 `model_registry_index.json`），含版本、特徵 Hash、Annotation Checksum。
*   **`GET /api/v1/training/models/:model_id/feature-manifest`**
    *   **用途**: 取得特定模型的 Feature Manifest（特徵順序、縮放參數、設備限制），供前端顯示模型詳情。

### 2.4 最佳化與模型推論 (Optimization Engine v1.2)
*   **`POST /api/v1/optimization/simulate`**
    *   **用途**: 啟動特定案場的冰水主機房排程最佳化。
    *   **Payload**: 指定預測區間 (如未來 24 小時)、天氣預報條件、使用的模型版本。
    *   **Response**: 返回 `task_id`。
*   **`GET /api/v1/optimization/results/:task_id`**
    *   **用途**: 抓取最佳化結果，將 Python DataFrame 轉換為前端可繪製圖表的 JSON（含 Baseline vs Optimized 對比、設備排程建議）。

### 2.5 設備驗證與品質報表 (Equipment Validation & Quality)
*   **`GET /api/v1/equipment-validation/:site_id/summary`**
    *   **用途**: 取得案場的設備邏輯驗證摘要（違規總數、違規類型、嚴重度分佈）。
*   **`GET /api/v1/equipment-validation/:site_id/violations`**
    *   **用途**: 分頁查詢設備邏輯違規明細（時間點、設備 ID、約束類型 E353-E357）。
*   **`GET /api/v1/quality/:site_id/flags-summary`**
    *   **用途**: 取得 Quality Flags 統計摘要（FROZEN / OUTLIER / HEAT_IMBALANCE / SENSOR_OFFLINE 各比例）。

### 2.6 混合模型一致性檢查 (Hybrid Consistency)
*   **`GET /api/v1/models/:model_id/consistency-report`**
    *   **用途**: 取得 Hybrid 模式模型的一致性報告（System vs Component 加總差異、偏差指標 E750-E759）。

### 2.7 系統健康檢查 (System Health)
*   **`GET /api/v1/health`**
    *   **用途**: 系統健康狀態。
    *   **Response**: 包含模組版本相容性矩陣驗證結果、SSOT 同步狀態、Pipeline 就緒狀態。
*   **`GET /api/v1/health/version-matrix`**
    *   **用途**: 返回當前模組版本組合及其相容性等級（🟢 完全相容 / 🟡 部分相容 / 🔴 不相容），對齊 Interface Contract v1.1 §5.2。

---

## 3. 非同步任務追蹤與錯誤映射 (Error Mapping)

由於底層作業 (如 `Model Training`) 可能長達數十分鐘，必須建立標準化的非同步任務狀態機。

### 3.1 狀態機生命週期
`CREATED` -> `PENDING` -> `RUNNING` -> `SUCCESS` / `FAILED` / `CANCELLED`

### 3.2 完整錯誤代碼傳遞 (E000 - E999)

當底層 Python 拋出依據 `PRD_Interface_Contract_v1.1` 定義的錯誤代碼時，Web 應用層應作如下封裝轉譯：

| 底層代碼 | 層級 | 意義 | Web Backend 處理方式 | 前端 UI 呈現建議 |
|:---|:---:|:---|:---|:---|
| **E000** | 全域 | Pipeline 時間基準遺失 | Task 標記 `FAILED` | 系統級錯誤，提示管理員檢查 Pipeline 初始化 |
| **E0xx** | 系統 | 編碼/記憶體/設定檔錯誤 | Task 標記 `FAILED` | 彈出 Alert，顯示系統級錯誤詳情 |
| **E1xx** | Parser | 解析錯誤 / 欄位遺失 / 標頭正規化失敗 | Task 標記 `FAILED` | 終止動畫，顯示缺少的欄位或編碼問題，提示重新上傳檔案 |
| **E2xx** | Cleaner | 資料清洗驗證失敗 / Quality Flags 異常 | Task 標記 `FAILED` 或 `SUCCESS`+Warnings | 顯示清洗結果摘要，標記異常欄位 |
| **E3xx** | Batch | Manifest 完整性 / Parquet 格式違規 | Task 標記 `FAILED` | 顯示批次處理錯誤詳情，建議重新執行 ETL |
| **E35x** | Equipment | 違反設備邏輯約束 (requires/mutex/sequence) | Task 標記 `SUCCESS`+Violations | 顯示違規設備清單與限制類型，建議確認系統設定 |
| **E4xx** | Annotation | Feature Annotation 版本/同步/格式錯誤 | Task 標記 `FAILED` | 提示執行 `excel_to_yaml.py` 或升級 Feature Template |
| **E5xx** | Governance | 架構違規（device_role 外洩 E500 / 直接寫入 YAML E501） | Task 標記 `FAILED` | 系統架構錯誤，記錄告警至 App DB，聯絡管理員 |
| **E6xx** | FE | 特徵工程錯誤（順序未記錄 E601 / 縮放遺失 E602） | Task 標記 `FAILED` | 顯示特徵矩陣錯誤，建議檢查 Feature Annotation 設定 |
| **E7xx** | Training | 訓練失敗 / 記憶體不足 / 驗證未通過 | Task 標記 `FAILED` | 建議聯絡系統管理員（資源擴容），顯示 Checkpoint 進度 |
| **E75x** | Hybrid | 混合模型一致性驗證失敗 | Task 標記 `FAILED` 或 `WARNING` | 顯示 System vs Component 差異報告 |
| **E8xx** | Optimization | 最佳化發散 / 約束不可行 / 天氣資料缺失 | Task 標記 `FAILED` | 具體的約束違規說明，建議調整參數或提供天氣資料 |
| **E9xx** | 跨階段 | 特徵對齊不匹配 (E901) / 維度錯誤 (E902) / 縮放不一致 (E903) / 設備限制不一致 (E904) | Task 標記 `FAILED` | 提示重新訓練模型或檢查特徵配置，顯示具體錯位資訊 |
| **W4xx** | 警告 | 數據警告 (不中斷): 平均值偏離、零值比過高 | Task 標記 `SUCCESS` | 提供 "Warnings" 列表，顯示在 Dashboard 通知中心 |

### 3.3 Warning 代碼（不中斷流程）

| Warning 代碼 | 說明 | 前端呈現 |
|:---|:---|:---|
| **W401** | MEAN_OUT_OF_RANGE | 統計均值偏離合理區間 |
| **W402** | STD_ANOMALY | 標準差異常偏大 |
| **W403** | HIGH_ZERO_RATIO | 零值比例過高（可能感測器故障） |
| **W404** | AFFINITY_VIOLATION | 質量守恆偏差 > 15% |
| **W405** | TIMESTAMP_GAP | 時間序列存在缺漏 |
| **W406** | UNIT_CONVERSION_APPROX | 單位轉換使用近似值 |
| **W407** | QUALITY_DEGRADATION | 整體品質下降 |

---

## 4. 前端資料結構與 Dashboard Schema

為了避免前端直接處理數千萬筆的 Raw Parquet Data，Web Backend 需要提供匯總 (Aggregated) 過的 JSON。

### 4.1 時間序列圖表用資料格式 (Time-series Data)
**`GET /api/v1/metrics/timeseries?site_id=...&start_time=...&end_time=...`**
```json
{
  "site_id": "cgmh_ty",
  "temporal_baseline": "2026-02-14T00:00:00Z",
  "pipeline_origin_timestamp": "2026-02-14T00:00:00.000000000Z",
  "resolution": "15m",
  "data": [
    {
      "timestamp": "2026-02-14T00:15:00Z",
      "chiller_01_power_kw": 420.5,
      "chiller_02_power_kw": 0,
      "system_cop": 4.8,
      "quality_flags": ["FROZEN"]
    }
  ],
  "quality_summary": {
    "total_rows": 96,
    "flagged_rows": 12,
    "flags_distribution": {
      "FROZEN": 5,
      "OUTLIER": 3,
      "HEAT_IMBALANCE": 2,
      "SENSOR_OFFLINE": 2
    }
  }
}
```

### 4.2 最佳化情境對比 (Baseline vs Optimized)
```json
{
  "scenario_comparison": {
    "total_energy_baseline_kwh": 12500,
    "total_energy_optimized_kwh": 11200,
    "savings_percent": 10.4,
    "model_version": "1.3",
    "feature_alignment_status": "VERIFIED",
    "equipment_constraint_status": "CONSISTENT",
    "recommended_actions": [
      {
        "timestamp": "2026-02-14T14:00:00Z",
        "action": "TURN_ON",
        "equipment": "CH-02",
        "reason": "預測負載突破 CH-01 最高效率區間",
        "constraint_ref": "E354_min_runtime_policy"
      }
    ]
  }
}
```

### 4.3 設備驗證摘要 (Equipment Validation Summary)
```json
{
  "site_id": "cgmh_ty",
  "validation_period": "2026-02-14T00:00:00Z / 2026-02-14T23:59:59Z",
  "total_violations": 15,
  "violations_by_type": {
    "E353_REQUIRES_VIOLATION": 8,
    "E354_MUTEX_VIOLATION": 2,
    "E355_SEQUENCE_VIOLATION": 3,
    "E356_MIN_RUNTIME_VIOLATION": 1,
    "E357_MIN_DOWNTIME_VIOLATION": 1
  },
  "severity_distribution": {
    "critical": 3,
    "warning": 12
  }
}
```

### 4.4 Pipeline 元資料 (Pipeline Metadata)
**`GET /api/v1/pipeline/metadata/:batch_id`**
```json
{
  "batch_id": "uuid-xxx",
  "pipeline_origin_timestamp": "2026-02-14T00:00:00.000000000Z",
  "module_versions": {
    "parser": "v2.1",
    "cleaner": "v2.2",
    "batch_processor": "v1.3",
    "feature_engineer": "v1.3"
  },
  "annotation_audit": {
    "schema_version": "1.3",
    "inheritance_chain": "base -> cgmh_ty",
    "editor": "王工程師",
    "last_updated": "2026-02-14T10:00:00Z"
  },
  "compatibility_status": "FULL_COMPATIBLE"
}
```

---

## 5. Web 應用層資料庫 (App Database) 職責

在底層架構中，Parquet / CSV 用於時序數據，YAML 用於 Feature SSOT。
但在 Web 應用層，我們需要一個關聯式資料庫 (如 PostgreSQL / MySQL) 負責以下工作：

1. **User & Authentication**: 帳號密碼、RBAC(Role-Based Access Control) 表，支援多租戶 (如廠務工程師、系統管理員)。
2. **Task Logs**: 記錄 `task_id`, `type` (ETL / TRAINING / OPTIMIZATION), `status`, `submit_time`, `end_time`, `error_code`, `error_message`, `pipeline_origin_timestamp`。
3. **Application Settings**: 前端儀表板的使用者偏好佈景 (Dashboard Layout)、通知偏好等與 ML 無關的狀態。
4. **Model Registry (Web 快取)**: 快取 `model_registry_index.json` 的關鍵欄位，方便前端查詢模型列表、版本狀態、Feature Manifest Hash、Annotation Checksum。
5. **Equipment Validation Audit**: 記錄每次 Pipeline 執行的設備邏輯驗證結果（違規次數、違規類型分佈），支援歷史趨勢查看。
6. **Annotation Change Log**: 記錄 Feature Annotation 的變更歷史（誰、何時、改了什麼），供稽核追蹤。

---

## 6. Temporal Baseline 在 Web 層的傳遞規範

### 6.1 傳遞路徑
底層 Python Worker 的 `PipelineContext.pipeline_timestamp` 必須在以下節點傳遞至 Web 層：

1. **Task 創建時**: 底層 Worker 啟動後，將 `pipeline_origin_timestamp` 寫入 Message Queue 的 Task Metadata。
2. **進度回報時**: WebSocket `TASK_UPDATE` 事件需包含 `pipeline_origin_timestamp` 欄位。
3. **結果儲存時**: Task 完成後，`pipeline_origin_timestamp` 寫入 App DB 的 Task Logs 表。
4. **API 回傳時**: `GET /api/v1/pipeline/tasks/:task_id` 回傳中包含此欄位。

### 6.2 前端呈現
- Dashboard 的「資料截止時間」顯示 `pipeline_origin_timestamp`（而非結果抓取時間）。
- 若前端發現 `pipeline_origin_timestamp` 距今超過 1 小時，顯示 ⚠️ 警告圖示（對齊 E000-W 邏輯）。

---

## 7. 下一步執行清單 (Next Steps)

1. **確認技術棧**: Web 團隊確認 Backend (Node.js/Python FastAPI/Golang) 與 Frontend (React/Vue) 使用的明確技術矩陣。
2. **設計 OpenAPI (Swagger)**: Backend 開發者依據第 2 節架構，產出明確的 `swagger.yaml` 介面文件，涵蓋全部 7 組 API 群組。
3. **對接 Python 指令**: 定義 Backend 如何啟動 ETL (e.g. 透過 `subprocess`、Airflow API 或是 Celery 佇列)。
4. **WebSocket 實作測試**: 測試長時間運行的最佳化演算與模型訓練的進度推播，是否會發生連線 Timeout。
5. **Error Code Mapping 互動規格**: 與前端工程師確認 Error Badge Component 的 UI Spec（顏色、圖示、彈窗行為），確保覆蓋 E000-E999。
6. **Model Registry 同步策略**: 決定 App DB 的 Model Registry 快取是定期同步（Cron）還是事件驅動（Training 完成後推送）。
7. **Equipment Validation Dashboard**: 設計設備邏輯違規的歷史趨勢圖表與告警門檻配置介面。
