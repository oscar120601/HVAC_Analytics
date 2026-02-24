# PRD v1.1: Web API 介面規格設計 (Web API Interface Specifications)

**文件版本:** v1.1 (Full Pipeline Coverage & Interface Contract v1.1 Alignment)  
**日期:** 2026-02-23  
**範圍:** 定義前後端與底層任務佇列之間的 RESTful API 與 WebSocket 介面規範，涵蓋 ETL、Feature Annotation、Model Training、Optimization、Equipment Validation、Hybrid Consistency 以及系統健康檢查。
**相依文件:** 
- PRD_Web_Application_Architecture_V1.1.md
- PRD_Interface_Contract_v1.1.md
- PRD_Feature_Annotation_Specification_V1.3.md
- PRD_Model_Training_v1.3.md
- PRD_Chiller_Plant_Optimization_V1.2.md
- PRD_Equipment_Dependency_Validation_v1.0.md

**修訂紀錄 (v1.0 → v1.1):**
- 新增 Model Training API（start, checkpoint, model registry）
- 新增 Equipment Validation API（summary, violations）
- 新增 Hybrid Consistency API（consistency-report）
- Feature Annotation API 擴充（Group Policies, Equipment Constraints, Excel 上傳）
- 新增系統健康檢查 API（health, version-matrix）
- 新增 Temporal Baseline 查詢 API
- WebSocket 事件新增 `TRAINING_PROGRESS`、`EQUIPMENT_ALERT`、`CONSISTENCY_CHECK`

**修訂紀錄 (v1.1 → v1.1.1):**
- ETL Pipeline API 擴充：支援多檔案上傳（`files` 參數取代單一 `file`）
- 新增資料夾批次上傳支援，系統自動過濾 CSV 檔案
- 更新 API Response 格式，新增 `files_processed` 欄位

---

## 1. 總覽與約定 (General Conventions)

*   **API Base Path**: `/api/v1`
*   **Request & Response Format**: `application/json`
*   **認證方式 (Authentication)**: Bearer Token (JWT), `Authorization: Bearer <token>`
*   **時間戳格式**: ISO 8601 UTC (例如：`2026-02-14T10:00:00.000Z`)
*   **分頁機制 (Pagination)**: `?page=1&limit=50`，回應一律包裝為 `{ "data": [...], "meta": { "total": 100, "page": 1, "limit": 50 } }`
*   **錯誤回應格式 (Error Response)**:
    ```json
    {
      "error": {
        "code": "E901",
        "name": "FEATURE_ALIGNMENT_MISMATCH",
        "message": "特徵對齊錯誤: 索引 3 預期 'wb_temp'，實際 'chwst_temp'",
        "severity": "CRITICAL",
        "recoverable": false,
        "details": {}
      }
    }
    ```

---

## 2. 認證與授權 (Auth & RBAC)

### 2.1 登入並取得 Token
*   **Endpoint**: `POST /api/v1/auth/login`
*   **Payload**:
    ```json
    { "username": "admin", "password": "secure_pwd" }
    ```
*   **Response (200 OK)**:
    ```json
    {
      "access_token": "ey...",
      "refresh_token": "ey...",
      "user": {
        "id": "usr_123",
        "role": "admin",
        "site_id": "cgmh_ty"
      }
    }
    ```

---

## 3. 非同步任務管理 (Async Task Management)

底層 Python ETL、Model Training 與 Optimization 耗時較長，所有的發布請求皆返回 HTTP 202 與 `task_id`。

### 3.1 查詢單一任務進度
*   **Endpoint**: `GET /api/v1/tasks/:task_id`
*   **Response (200 OK)**:
    ```json
    {
      "task_id": "uuid-12345",
      "type": "MODEL_TRAINING",
      "status": "RUNNING",
      "progress_percent": 45,
      "current_stage": "CROSS_VALIDATION",
      "pipeline_origin_timestamp": "2026-02-14T10:00:00.000000000Z",
      "submit_time": "2026-02-14T10:00:00Z",
      "result_url": null,
      "errors": [],
      "warnings": [
        { "code": "W401", "message": "MEAN_OUT_OF_RANGE", "target": "chiller_01_chwst" }
      ],
      "equipment_validation_summary": {
        "total_violations": 3,
        "critical_count": 1
      }
    }
    ```

### 3.2 終止執行中的任務
*   **Endpoint**: `POST /api/v1/tasks/:task_id/cancel`
*   **Response (200 OK)**: `{ "status": "CANCELLED" }`

### 3.3 任務列表 (含歷史)
*   **Endpoint**: `GET /api/v1/tasks?type=ETL&status=FAILED&page=1&limit=20`
*   **Response (200 OK)**: 分頁回傳任務清單，含 `pipeline_origin_timestamp` 與錯誤代碼摘要。

---

## 4. Pipeline 與資料清洗 (ETL Pipeline Endpoints)

### 4.1 上傳資料並啟動 ETL
*   **Endpoint**: `POST /api/v1/pipeline/batch`
*   **Content-Type**: `multipart/form-data`
*   **Payload**:
    *   `files`: (CSV Files, 支援多檔案) 原始資料檔案，支援批次上傳多個 CSV 檔案或資料夾。
    *   `site_id`: "cgmh_ty"
*   **支援功能**:
    *   **多檔案上傳**: 可同時上傳多個 CSV 檔案進行批次處理
    *   **資料夾選擇**: 支援上傳整個資料夾，系統自動過濾其中的 CSV 檔案
    *   **自動過濾**: 非 CSV 檔案會被自動忽略
*   **Response (202 Accepted)**:
    ```json
    {
      "message": "ETL job started.",
      "task_id": "task_etl_98765",
      "files_processed": 1,
      "pipeline_origin_timestamp": "2026-02-14T10:00:00.000000000Z"
    }
    ```

### 4.2 查詢 Pipeline 時間基準
*   **Endpoint**: `GET /api/v1/pipeline/temporal-context`
*   **Response (200 OK)**:
    ```json
    {
      "pipeline_origin_timestamp": "2026-02-14T10:00:00.000000000Z",
      "site_id": "cgmh_ty",
      "elapsed_seconds": 125.4,
      "baseline_version": "1.0",
      "is_stale": false
    }
    ```

### 4.3 查詢 Pipeline 元資料
*   **Endpoint**: `GET /api/v1/pipeline/metadata/:batch_id`
*   **Response (200 OK)**:
    ```json
    {
      "batch_id": "uuid-xxx",
      "pipeline_origin_timestamp": "2026-02-14T00:00:00.000000000Z",
      "module_versions": {
        "parser": "v2.1", "cleaner": "v2.2",
        "batch_processor": "v1.3", "feature_engineer": "v1.3"
      },
      "annotation_audit": {
        "schema_version": "1.3",
        "inheritance_chain": "base -> cgmh_ty",
        "editor": "王工程師"
      },
      "compatibility_status": "FULL_COMPATIBLE"
    }
    ```

---

## 5. 設備標註與設定 (Feature Annotation v1.3 & Site Setup)
*取代原本文本化的 Wizard CLI，透過 API 控制 YAML SSOT (經由 `excel_to_yaml.py` 安全封裝)*

### 5.1 取得目前的設備註解 (Column Annotations)
*   **Endpoint**: `GET /api/v1/facilities/:site_id/equipment/annotations`
*   **Response (200 OK)**:
    ```json
    {
      "site_id": "cgmh_ty",
      "schema_version": "1.3",
      "template_version": "1.3",
      "last_updated": "2026-02-14T10:00:00Z",
      "editor": "王工程師",
      "columns": [
        {
          "column_name": "chiller_01_chwst",
          "physical_type": "temperature",
          "unit": "°C",
          "device_role": "primary",
          "is_target": false,
          "enable_lag": true,
          "lag_intervals": [1, 4, 96],
          "equipment_id": "CH-01",
          "ignore_warnings": [],
          "status": "confirmed"
        }
      ]
    }
    ```

### 5.2 提交標註更新 (Submit Annotations)
*   **Endpoint**: `PUT /api/v1/facilities/:site_id/equipment/annotations`
*   **Payload**: 傳遞被修改的 `columns` 陣列。
*   **Validation**:
    - `is_target=true` + `enable_lag=true` 觸發 E405 錯誤
    - 欄位名稱不在 CSV 中觸發 E401 錯誤
*   **Response (200 OK)**: `{ "message": "Annotations updated successfully.", "sync_status": "YAML_GENERATED" }`
    *(註: 後端實作必須呼叫底層 Python 腳本產生 YAML，並處理 `E501` 鎖定錯誤)*

### 5.3 取得/更新 Group Policies
*   **GET** `GET /api/v1/facilities/:site_id/group-policies`
*   **PUT** `PUT /api/v1/facilities/:site_id/group-policies`
*   **Response**: 
    ```json
    {
      "policies": [
        {
          "name": "chillers_temp",
          "match_type": "prefix",
          "match_value": "chiller_",
          "physical_type": "temperature",
          "template": "Standard_Chiller",
          "equipment_category": "冰水主機"
        }
      ]
    }
    ```

### 5.4 取得/更新 Equipment Constraints
*   **GET** `GET /api/v1/facilities/:site_id/equipment-constraints`
*   **PUT** `PUT /api/v1/facilities/:site_id/equipment-constraints`
*   **Response**:
    ```json
    {
      "constraints": [
        {
          "id": "chiller_pump_interlock",
          "description": "冰水主機開啟時必須有對應冰水泵運轉",
          "check_type": "requires",
          "trigger_status": ["chiller_01_status"],
          "required_status": ["chw_pump_01_status", "chw_pump_02_status"],
          "severity": "critical"
        }
      ]
    }
    ```

### 5.5 上傳 Excel 並觸發同步
*   **Endpoint**: `POST /api/v1/facilities/:site_id/annotation/upload-excel`
*   **Content-Type**: `multipart/form-data`
*   **Response (202 Accepted)**:
    ```json
    {
      "message": "Excel uploaded, conversion started.",
      "task_id": "task_sync_111",
      "sync_checks": {
        "template_version_valid": true,
        "e406_sync_status": "PROCESSING"
      }
    }
    ```

---

## 6. 模型訓練 (Model Training v1.3)

### 6.1 啟動模型訓練
*   **Endpoint**: `POST /api/v1/training/start`
*   **Payload**:
    ```json
    {
      "site_id": "cgmh_ty",
      "training_mode": "hybrid",
      "target_variables": ["system_total_kw"],
      "model_types": ["xgboost", "lightgbm"],
      "hyperparameter_config": {
        "n_estimators": [100, 200, 500],
        "max_depth": [3, 5, 7]
      },
      "resource_limits": {
        "max_memory_gb": 8,
        "max_cpu_cores": 4,
        "timeout_minutes": 120
      }
    }
    ```
*   **Response (202 Accepted)**:
    ```json
    {
      "task_id": "task_train_789",
      "resource_estimate": {
        "estimated_memory_gb": 4.2,
        "estimated_duration_minutes": 45,
        "resource_status": "SUFFICIENT"
      }
    }
    ```

### 6.2 查詢訓練 Checkpoint 進度
*   **Endpoint**: `GET /api/v1/training/tasks/:task_id/checkpoint`
*   **Response (200 OK)**:
    ```json
    {
      "task_id": "task_train_789",
      "checkpoint": {
        "current_fold": 3,
        "total_folds": 5,
        "best_mape_so_far": 4.2,
        "current_model_type": "xgboost",
        "checkpoint_saved_at": "2026-02-14T10:30:00Z"
      },
      "resource_usage": {
        "memory_used_gb": 3.8,
        "cpu_utilization_percent": 85,
        "elapsed_minutes": 22
      }
    }
    ```

### 6.3 列出已註冊模型
*   **Endpoint**: `GET /api/v1/training/models?site_id=cgmh_ty`
*   **Response (200 OK)**:
    ```json
    {
      "data": [
        {
          "model_id": "model_cgmh_001",
          "site_id": "cgmh_ty",
          "training_mode": "hybrid",
          "target": "system_total_kw",
          "created_at": "2026-02-14T10:30:00Z",
          "mape": 3.8,
          "feature_hash": "sha256:a1b2c3d4...",
          "annotation_checksum": "sha256:e5f6g7h8...",
          "equipment_constraints": ["chiller_pump_mutex", "min_runtime_15min"],
          "alignment_status": "VERIFIED"
        }
      ]
    }
    ```

### 6.4 取得模型 Feature Manifest
*   **Endpoint**: `GET /api/v1/training/models/:model_id/feature-manifest`
*   **Response (200 OK)**:
    ```json
    {
      "manifest_version": "2.0-ALIGN",
      "feature_specification": {
        "feature_names": ["chiller_1_load", "chiller_2_load", "wb_temp", "chwst_temp"],
        "feature_count": 4,
        "feature_hash": "sha256:a1b2c3d4..."
      },
      "scaling_specification": {
        "scaler_type": "StandardScaler",
        "scaler_params": {
          "mean_": [450.5, 420.3, 28.5, 7.2],
          "scale_": [120.2, 115.8, 2.1, 0.5]
        }
      },
      "equipment_constraints": {
        "constraints_applied": ["chiller_pump_mutex", "min_runtime_15min"],
        "validation_enabled": true
      }
    }
    ```

---

## 7. 最佳化演算與模型預測 (Optimization v1.2 & Inference)

### 7.1 執行最佳化模擬 (Trigger Optimization Simulation)
*   **Endpoint**: `POST /api/v1/optimization/simulate`
*   **Payload**:
    ```json
    {
      "site_id": "cgmh_ty",
      "model_id": "model_cgmh_001",
      "forecast_horizon_hours": 24,
      "objective": "MINIMIZE_ENERGY",
      "weather_override": {
        "avg_temp_c": 32.5,
        "humidity_percent": 80
      }
    }
    ```
*   **Response (202 Accepted)**:
    ```json
    {
      "task_id": "task_opt_456",
      "feature_alignment_check": "PASSED",
      "equipment_constraint_check": "CONSISTENT"
    }
    ```

### 7.2 取得最佳化報表數據 (Get Optimization Results)
*為繪圖庫 (ECharts / Chart.js / Highcharts) 準備的輕量級格式*
*   **Endpoint**: `GET /api/v1/optimization/results/:task_id`
*   **Response (200 OK)**:
    ```json
    {
      "summary": {
        "baseline_energy_kwh": 35000,
        "optimized_energy_kwh": 31000,
        "saving_ratio_percent": 11.4,
        "model_version": "1.3",
        "feature_alignment_status": "VERIFIED"
      },
      "series": {
        "timestamps": ["2026-02-14T00:00:00Z", "2026-02-14T01:00:00Z"],
        "baseline_power": [1400.5, 1420.2],
        "optimized_power": [1250.0, 1260.4]
      },
      "device_schedules": [
        {
          "equipment_id": "CH-01",
          "action": "TURN_OFF",
          "timestamp": "2026-02-14T02:00:00Z",
          "reason": "load_min_limit E354 policy applied",
          "constraint_ref": "min_runtime_15min"
        }
      ]
    }
    ```

---

## 8. 設備驗證與品質報表 (Equipment Validation & Quality)

### 8.1 設備邏輯驗證摘要
*   **Endpoint**: `GET /api/v1/equipment-validation/:site_id/summary`
*   **Response (200 OK)**:
    ```json
    {
      "site_id": "cgmh_ty",
      "validation_period": {
        "start": "2026-02-14T00:00:00Z",
        "end": "2026-02-14T23:59:59Z"
      },
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
      },
      "trend": "IMPROVING"
    }
    ```

### 8.2 設備邏輯違規明細
*   **Endpoint**: `GET /api/v1/equipment-validation/:site_id/violations?page=1&limit=20`
*   **Response (200 OK)**:
    ```json
    {
      "data": [
        {
          "violation_id": "viol_001",
          "timestamp": "2026-02-14T14:15:00Z",
          "constraint_id": "chiller_pump_interlock",
          "error_code": "E353",
          "trigger_equipment": "chiller_01",
          "missing_requirement": "chw_pump_01",
          "severity": "critical",
          "quality_flag_applied": "REQUIRES_VIOLATION"
        }
      ],
      "meta": { "total": 15, "page": 1, "limit": 20 }
    }
    ```

### 8.3 Quality Flags 統計摘要
*   **Endpoint**: `GET /api/v1/quality/:site_id/flags-summary?start_time=...&end_time=...`
*   **Response (200 OK)**:
    ```json
    {
      "site_id": "cgmh_ty",
      "total_rows": 9600,
      "flagged_rows": 480,
      "quality_score": 95.0,
      "flags_distribution": {
        "FROZEN": 120,
        "OUTLIER": 85,
        "HEAT_IMBALANCE": 60,
        "AFFINITY_VIOLATION": 45,
        "INSUFFICIENT_DATA": 90,
        "SENSOR_OFFLINE": 80
      }
    }
    ```

---

## 9. 混合模型一致性檢查 (Hybrid Consistency)

### 9.1 取得一致性報告
*   **Endpoint**: `GET /api/v1/models/:model_id/consistency-report`
*   **Response (200 OK)**:
    ```json
    {
      "model_id": "model_cgmh_001",
      "training_mode": "hybrid",
      "consistency_checks": {
        "system_vs_component_discrepancy_percent": 3.2,
        "severity": "normal",
        "systematic_bias_detected": false,
        "trend_correlation": 0.97,
        "light_load_variance_elevated": true
      },
      "error_codes_triggered": ["E757", "E758"],
      "recommendation": "差異在可接受範圍 (<=5%)，以 System Model 為準"
    }
    ```

---

## 10. 系統健康檢查 (System Health)

### 10.1 基本健康狀態
*   **Endpoint**: `GET /api/v1/health`
*   **Response (200 OK)**:
    ```json
    {
      "status": "HEALTHY",
      "timestamp": "2026-02-14T10:00:00Z",
      "components": {
        "database": "OK",
        "message_queue": "OK",
        "python_worker": "OK",
        "yaml_ssot_sync": "SYNCED"
      },
      "pipeline_ready": true,
      "active_tasks": 2
    }
    ```

### 10.2 模組版本相容性矩陣
*   **Endpoint**: `GET /api/v1/health/version-matrix`
*   **Response (200 OK)**:
    ```json
    {
      "compatibility_status": "FULL_COMPATIBLE",
      "modules": {
        "parser": { "version": "v2.1", "status": "OK" },
        "cleaner": { "version": "v2.2", "status": "OK" },
        "batch_processor": { "version": "v1.3", "status": "OK" },
        "feature_engineer": { "version": "v1.3", "status": "OK" },
        "model_training": { "version": "v1.3", "status": "OK" },
        "optimization": { "version": "v1.2", "status": "OK" },
        "equipment_validation": { "version": "v1.0", "status": "OK" },
        "feature_annotation": { "version": "v1.3", "status": "OK" }
      },
      "upgrade_recommendations": []
    }
    ```

---

## 11. 即時通訊 (WebSocket)
供前端建立連接，監聽底層傳來的非同步狀態。
*   **URL**: `wss://[domain]/api/v1/ws/stream?token=[jwt]`

### 11.1 Event: `TASK_UPDATE`
```json
{
  "event": "TASK_UPDATE",
  "task_id": "uuid-12345",
  "progress": 75,
  "status": "RUNNING",
  "current_stage": "FEATURE_ENGINEER",
  "pipeline_origin_timestamp": "2026-02-14T10:00:00.000000000Z",
  "message": "Generating Feature Matrix..."
}
```

### 11.2 Event: `SYSTEM_ALERT`
```json
{
  "event": "SYSTEM_ALERT",
  "level": "CRITICAL",
  "code": "E355",
  "message": "主機關閉後最少停機 10 分鐘，發現 Sequence Violation",
  "equipment_id": "CH-01",
  "constraint_ref": "min_downtime_10min"
}
```

### 11.3 Event: `TRAINING_PROGRESS`
```json
{
  "event": "TRAINING_PROGRESS",
  "task_id": "task_train_789",
  "current_fold": 3,
  "total_folds": 5,
  "best_mape": 4.2,
  "current_model": "xgboost",
  "resource_usage": {
    "memory_used_gb": 3.8,
    "cpu_percent": 85
  }
}
```

### 11.4 Event: `EQUIPMENT_ALERT`
```json
{
  "event": "EQUIPMENT_ALERT",
  "site_id": "cgmh_ty",
  "violation": {
    "code": "E353",
    "constraint_id": "chiller_pump_interlock",
    "trigger": "chiller_01",
    "missing": "chw_pump_01",
    "severity": "critical",
    "timestamp": "2026-02-14T14:15:00Z"
  }
}
```

### 11.5 Event: `CONSISTENCY_CHECK`
```json
{
  "event": "CONSISTENCY_CHECK",
  "model_id": "model_cgmh_001",
  "discrepancy_percent": 3.2,
  "severity": "normal",
  "codes": ["E757"]
}
```
