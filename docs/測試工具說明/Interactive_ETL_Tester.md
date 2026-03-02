# 🧪 全域互動式 ETL 測試工具 (Interactive ETL Tester)

**文件版本**: v2.1 實作版  
**最後更新**: 2026-03-02  
**對應專案階段**: Sprint 2 完成 (v1.7.0~v2.0.0) | Sprint 3 就緒

---

## 📋 文件導覽

| 區塊 | 內容 | 狀態 |
|:---|:---|:---:|
| [第一部分](#一部分已完成功能現況) | 已上線功能 (v1.6.0 + v1.7.0~v2.0.0) | ✅ 已完成 |
| [第二部分](#二部分待實作項目) | Sprint 3 待实作項目 | ⏳ 規劃中 |
| [第三部分](#三部分相關prd文件) | 相關 PRD 文件索引 | 📎 參考用 |

---

## 一部分：已完成功能現況

### 1.1 工具概述

**目標**：提供一個無需手動輸入終端機指令，透過網頁即可完整體驗從資料解析、特徵標註、設備預檢與批次落地的互動式測試平台。

**核心設計理念**：**Step 1 → Step 2 無縫整合**
- Step 1 解析 CSV 後，Step 2 **直接沿用**解析結果產生 Excel，無需重新上傳 CSV
- 確保欄位名稱從 Step 1 到 Step 4 **完全一致**，避免 E409 (Header Annotation Mismatch) 錯誤

**檔案位置**：
- **後端 API**: `tools/demo/test_server.py` (FastAPI)
- **前端 UI**: `tools/demo/tester.html` (HTML + CSS + JS)

**啟動方式**：
```bash
uvicorn tools.demo.test_server:app --reload --port 8000 --host 0.0.0.0
```

---

### 1.2 四步驟測試流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 1: Parser 預覽  →  Step 2: Excel 範本  →  Step 3: YAML 轉換  →  Step 4: ETL 執行  │
│       ↓                      ↍                      ↓                    ↓       │
│  上傳 CSV 預覽          填寫標註資訊           轉換為 SSOT        完整管線清洗與輸出   │
│  選擇 Parser 類型       產生 Excel 範本        驗證欄位契約       查看拓樸摘要與圖表   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑
                                      └─ Pipeline 初始化狀態指示器 (Gap 4)
```

| 步驟 | 功能 | API 端點 | 核心機制 |
|:---:|:---|:---|:---|
| **Step 1** | 選擇 Parser 並解析 CSV | `POST /api/v1/pipeline/parse-preview` | `ParserFactory` 策略模式 |
| **Step 1.5** | Pipeline 初始化狀態檢查 | `GET /api/pipeline/init-status` | DI 初始化驗證 |
| **Step 2** | 產生 Excel 標註範本 | `POST /api/generate-template-from-preview` | `FeatureAnnotationWizard` |
| **Step 3** | Excel 轉 YAML SSOT | `POST /api/convert-yaml` | `ExcelToYamlConverter` |
| **Step 4** | 執行完整 ETL Pipeline | `POST /api/run-pipeline` | `ETLContainer` + 背景任務 |

**支援 Parser 類型**：
- **通用 CSV**：標準 Date/Time 格式
- **Siemens Scheduler Report**：CGMH-TY, Farglory O3, KMUH 格式（含 Point_1~N 映射）

---

### 1.3 已實作功能總覽

#### ✅ v1.6.0 (Sprint 1)

| 功能 | 說明 | 驗收標準 |
|:---|:---|:---|
| **GNN 拓樸摘要面板** | Step 4 結果區顯示節點/邊緣統計 | 節點數、邊緣數、鄰接矩陣維度正確顯示 |
| **v1.4 視覺提示** | Step 2/3 顯示拓樸欄位說明 | topology_node_id, control_semantic, decay_factor 提示 |
| **診斷工具拓樸旗標** | 診斷 API 回傳 `topology_summary` | `has_topology`, `node_count`, `sample_nodes` 欄位 |
| **Excel 拓樸欄位提示** | 下載時顯示 v1.4 欄位說明 | 欄位用途說明正確呈現 |
| **Step 1→2 無縫整合** | 預覽結果直接產生 Excel，無需重傳 CSV | 欄位名稱完全一致 |

#### ✅ v1.7.0~v2.0.0 (Sprint 2 - 缺口實作)

| 版本 | 功能 | 對應缺口 | 實作文件 |
|:---:|:---|:---:|:---|
| **v1.7.0** | Excel 17 欄結構 (A-Q)，equipment_id 移至 I 欄，新增 6 個 v1.4 欄位 | 缺口一 | `wizard.py`, `excel_to_yaml.py` |
| **v1.8.0** | Manifest 契約元資料面板 + `device_role` 隔離檢查 | 缺口二 | `test_server.py`, `tester.html` |
| **v1.9.0** | 鄰接矩陣視覺化 (≤10 節點) + GNN 多任務指標面板 | 缺口三 | `test_server.py`, `tester.html` |
| **v2.0.0** | Pipeline 初始化狀態指示器 (E406/YAML 鎖定/Manager/Validator) | 缺口四 | `test_server.py`, `tester.html` |

---

### 1.4 Excel 範本欄位結構 (v1.4 規範) ✅ 已實作

**總計 17 欄 (A-Q)**，分四層組織：

```
第一層：核心欄位 (A-I)
├── A: column_name (欄位名稱)
├── B: physical_type (物理類型)
├── C: unit (單位)
├── D: device_role (設備角色)
├── E: is_target (是否目標)
├── F: enable_lag (啟用落後特徵)
├── G: lag_intervals (落後時間間隔)
├── H: ignore_warnings (忽略警告代碼)
└── I: equipment_id (設備代碼) ← v1.7.0 修正位置

第二層：拓樸與控制語意 (J-M) ← v1.7.0 新增
├── J: upstream_equipment_id (上游設備ID)
├── K: point_class (點位型態)
├── L: control_domain (控制域)
└── M: setpoint_pair_id (配對設定值ID)

第三層：國際標準標籤 (N-O) ← v1.7.0 新增
├── N: brick_schema_tag (Brick Schema)
└── O: haystack_tag (Haystack標籤)

第四層：人工註記 (P-Q)
├── P: description (中文描述)
└── Q: status (狀態)
```

**實作位置**：
- `tools/features/wizard.py`: `_initialize_sheets()` 定義 17 欄結構
- `tools/features/excel_to_yaml.py`: `header_map` 解析對應

---

### 1.5 Gap 實作詳情

#### Gap 2: Manifest 契約與 device_role 隔離檢查 (v1.8.0) ✅

**後端實作** (`test_server.py`):
```python
def _check_device_role_isolation(df: pl.DataFrame) -> dict:
    """檢查 device_role 是否隔離於 Parquet（不應存在）"""
    has_violation = 'device_role' in df.columns
    return {
        "status": "合規" if not has_violation else "違規",
        "violation_detail": f"發現 device_role 欄位" if has_violation else None
    }

# 診斷端點回傳新增
{
    "device_role_isolation": {...},
    "manifest_contract": {
        "pipeline_origin_timestamp": str,
        "annotation_checksum": str,
        ...
    }
}
```

**前端實作** (`tester.html`):
- `renderManifestContractPanel()` - 顯示時間基準、Checksum、E350 違規數
- `renderDeviceRoleIsolation()` - 顯示隔離檢查狀態

#### Gap 3: GNN 圖結構與多任務指標 (v1.9.0) ✅

**鄰接矩陣視覺化**:
```javascript
function renderAdjacencyMatrixPreview(topologyContext) {
    const { nodes, edges } = topologyContext;
    if (nodes.length > 10) {
        return `<div>Matrix: ${nodes.length}×${nodes.length} (too large)</div>`;
    }
    // 生成 N×N 表格
    const matrix = Array(n).fill(null).map(() => Array(n).fill(0));
    edges.forEach(edge => { matrix[srcIdx][tgtIdx] = 1; });
    return renderMatrixTable(matrix, nodes.map(n => n.id));
}
```

**GNN 多任務指標面板**:
```javascript
function renderGNNMetricsPanel(modelMetrics) {
    return `
        <div>Physics Discrepancy: ${metrics.physics.physics_discrepancy}</div>
        <div>Hybrid Warning: ${metrics.physics.e846_triggered ? 'E846' : '-'}</div>
        <div>Multi-Task R²: System=${r2.system}, Component=${r2.component}</div>
    `;
}
```

#### Gap 4: Pipeline 初始化狀態指示器 (v2.0.0) ✅

**API 端點**:
```python
@app.get("/api/pipeline/init-status")
async def get_pipeline_init_status(site_id: str):
    return {
        "e406_passed": _check_excel_yaml_sync(site_id),
        "yaml_locked": _check_yaml_file_lock(site_id),
        "manager_loaded": _check_feature_manager(site_id),
        "validator_ready": _check_equipment_validator(site_id),
        "pipeline_ready": all([...]),
        "stages": {...}
    }
```

**前端整合**:
- Step 1 成功後自動呼叫 `checkPipelineInitStatus()`
- 顯示四階段狀態：E406 稽核 → YAML 鎖定 → Manager 載入 → Validator 就緒
- `pipeline_ready` 為 true 時解鎖 Step 2 按鈕

---

## 二部分：待實作項目 (Sprint 3)

### 2.1 規劃中的功能

| 任務 ID | 任務描述 | 預估工時 | 優先級 | 計畫版本 | 前置條件 |
|:---:|:---|:---:|:---:|:---:|:---|
| **UI-009** | GNN Trainer 整合測試面板 | 2.0 天 | 🔴 High | v2.1.0 | `PRD_FEATURE_ENGINEER_V1.4.md` 部署 |
| **UI-010** | Hybrid Consistency 檢查視覺化 (E751-E758) | 1.5 天 | 🟡 Medium | v2.2.0 | `PRD_Hybrid_Model_Consistency_v1.0.md` |
| **UI-011** | 特徵工程即時預覽 | 2.0 天 | 🟡 Medium | v2.3.0 | Feature Engineer API 就緒 |

### 2.2 相依性說明

```
Sprint 3 (v2.1.0~v2.3.0):
├── UI-009: GNN Trainer 整合
│   ↑ 前置: Feature Engineer v1.4 部署完成
│   ↑ 前置: Model Training v1.4 就緒
│
└── UI-010: Hybrid Consistency 檢查
    ↑ 前置: Hybrid Model Consistency v1.0 就緒
```

---

## 三部分：相關 PRD 文件

### 3.1 已完成模組 PRD

| PRD 文件 | 版本 | 狀態 | 對應功能 |
|:---|:---:|:---:|:---|
| `PRD_Interface_Contract_v1.2.md` | v1.2 | ✅ 已完成 | 錯誤代碼體系 (E000-E999) |
| `PRD_System_Integration_v1.2.md` | v1.2 | ✅ 已完成 | PipelineContext、初始化順序 |
| `PRD_Feature_Annotation_Specification_V1.4.md` | v1.4.3 | ✅ 已完成 | Excel 範本、YAML SSOT |
| `PRD_Parser_V2.2.md` | v2.2 | ✅ 已完成 | Parser 策略模式 |
| `PRD_CLEANER_v2.2.md` | v2.2 | ✅ 已完成 | 資料清洗、設備邏輯預檢 |
| `PRD_BATCH_PROCESSOR_v1.3.md` | v1.3 | ✅ 已完成 | Parquet 輸出、Manifest |

### 3.2 進行中/待開發模組 PRD

| PRD 文件 | 版本 | 狀態 | 對應 Sprint |
|:---|:---:|:---:|:---:|
| `PRD_FEATURE_ENGINEER_V1.4.md` | v1.4.12 | ⏳ Sprint 3 | 特徵工程、GNN 資料匯出 |
| `PRD_Model_Training_v1.4.md` | v1.4.9 | ⏳ Sprint 3 | GNN Trainer、物理損失 |
| `PRD_Hybrid_Model_Consistency_v1.0.md` | v1.0 | ⏳ Sprint 3 | Hybrid Consistency |
| `PRD_Chiller_Plant_Optimization_V1.2.md` | v1.2 | ⏳ Sprint 4 | 最佳化引擎 |
| `PRD_Continual_Learning_v1.1.md` | v1.1 | ⏳ Sprint 4 | GEM、漂移檢測 |

---

## 附錄：API 端點清單

| 方法 | 端點 | 用途 | 版本 |
|:---:|:---|:---|:---:|
| GET | `/api/health` | 健康檢查 | v1.0 |
| GET | `/api/v1/parser/strategies` | 取得可用 Parser 類型 | v1.0 |
| POST | `/api/v1/pipeline/parse-preview` | Step 1: 解析 CSV 預覽 | v1.0 |
| **GET** | **`/api/pipeline/init-status`** | **Step 1.5: 初始化狀態檢查** | **v2.0** |
| POST | `/api/generate-template-from-preview` | Step 2: 產生 Excel | v1.5 |
| POST | `/api/convert-yaml` | Step 3: Excel 轉 YAML | v1.0 |
| POST | `/api/run-pipeline` | Step 4: 執行 ETL | v1.3 |
| GET | `/api/job-status/{job_id}` | 查詢背景任務 | v1.3 |
| GET | `/api/download-parquet/{site_id}` | 下載 Parquet | v1.2 |
| POST | `/api/diagnostic/parser` | 診斷：Parser | v1.3 |
| POST | `/api/diagnostic/cleaner` | 診斷：Cleaner | v1.3 |
| **POST** | **`/api/diagnostic/batch-processor`** | **診斷：含 Manifest/GNN 指標** | **v1.8~1.9** |
| POST | `/api/diagnostic/full` | 診斷：完整 ETLContainer | v1.3 |

---

*文件結束*
