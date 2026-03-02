# 🧪 全域互動式 ETL 測試工具 (Interactive ETL Tester)

## 📖 1. 工具總覽 (Overview)

**目標**：提供一個無需手動輸入終端機指令（Command Line），透過網頁即可完整體驗從資料解析、特徵標註、設備預檢與批次落地 (Sprint 1~5) 的單一互動式測試平台。

**核心設計理念**：**Step 1 → Step 2 無縫整合**

- Step 1 解析 CSV 後，Step 2 **直接沿用**解析結果產生 Excel，無需重新上傳 CSV
- 確保欄位名稱從 Step 1 到 Step 4 **完全一致**，避免 E409 (Header Annotation Mismatch) 錯誤

**位置**：

- **後端 API**: `tools/demo/test_server.py` (FastAPI)
- **前端 UI**: `tools/demo/tester.html` (HTML + CSS + JS)

## ⚙️ 2. 架構與功能 (Architecture & Features)

本測試工具總共涵蓋四個主要步驟，模擬真實的案場導入流程：

### 🔄 整合流程：Step 1 → Step 2（推薦）

```
Step 1: 解析 CSV 預覽 ───────┐
    │                        │
    ▼                        │
顯示 Parser 結果              │
(欄位列表、點位映射)          │
    │                        │
    ▼                        ▼
點擊「從預覽結果產生」   →   Step 2: Excel 標註範本
    │                        │
    ▼                        ▼
欄位名稱完全一致 ←───────────┘
(確保與 Step 4 ETL Pipeline 相容)
```

1. **Step 1: 選擇 Parser 並解析 CSV (`/api/v1/pipeline/parse-preview`)**
   - **背後機制**：呼叫 `ParserFactory` (`src/etl/parser/__init__.py`)
   - **核心功能**：
     - 上傳 CSV 後，系統顯示可用的 Parser 類型（通用、Siemens Scheduler、自動偵測）
     - 使用者手動選擇 Parser 類型（或選擇自動偵測）
     - 系統使用選定 Parser 解析 CSV，回傳預覽結果（欄位列表、點位映射、統計資訊）
   - **支援格式**：
     - **通用 CSV**：標準 Date/Time 格式
     - **Siemens Scheduler Report**：CGMH-TY, Farglory O3, KMUH 格式（含 Point_1~N 映射）
   - **與 Step 2 整合**：預覽成功後，可直接點擊「從預覽結果產生 Excel 範本」按鈕，無需重新上傳 CSV

2. **Step 2: 自動生成 Excel 標註範本 (`/api/generate-template-from-preview`)**
   - **推薦方式**：**從 Step 1 預覽結果產生**（預設選項）
     - 使用 Step 1 已解析的 `columns` 和 `point_mapping`
     - 確保欄位名稱與 Step 4 ETL Pipeline 完全一致
     - Excel `column_name` 顯示 Parser 標準化後的 snake_case 名稱
     - Excel `description` 顯示 Point_X → 原始監控點名稱對照（如 `[Point_1 | AHWP-3.KWH]`）
   - **背後機制**：呼叫 `FeatureAnnotationWizard.run_from_parser_result()` (`tools/features/wizard.py`)
   - **功能**：根據 Step 1 解析結果，系統自動分析並推測潛在的 HVAC 設備類型，產生帶有下拉選單與輔助提示的 Excel 檔案

3. **Step 3: 轉換 Excel 為 YAML SSOT (`/api/convert-yaml`)**
   - **背後機制**：呼叫 `ExcelToYamlConverter` (`tools/features/excel_to_yaml.py`)
   - **功能**：人工填寫完 Excel 後將其上傳，系統會檢查硬性約束 (E400, E403 等錯誤碼) 並產出為單一真相源 (`.yaml`) 檔案至 `config/features/sites/` 下
   - **欄位對應**：Excel 中的 `column_name`（標準化 snake_case 名稱）會成為 YAML 的欄位識別碼，與 Step 4 Parser 輸出的欄位名稱自動匹配

4. **Step 4: 執行完整 ETL Pipeline (`/api/run-pipeline`)**
   - **背後機制**：呼叫 `ETLContainer`, `PipelineContext`, 選定的 Parser, `DataCleaner` 以及 `BatchProcessor`
   - **功能**：輸入原始 CSV，系統將讀取 Step 3 產生的 YAML 設定檔。執行編碼偵測、時區校正、語意對應清洗與 E350 設備物理違規檢查，最後由 `BatchProcessor` 將資料落地，並返回清洗圖表、異常條目與 `Manifest v1.3`
   - **Parser 一致性保證**：此階段使用的 Parser 類型會自動與 Step 1 選擇的類型一致，確保欄位名稱標準化邏輯完全相同
   - **欄位匹配**：Step 4 Parser 輸出的標準化欄位名稱會與 Step 2 Excel / Step 3 YAML 中的 `column_name` 自動對應
   - **非同步執行**：
     - `POST /api/run-pipeline` 會立即回傳 `job_id`（`status=started`）
     - 前端會輪詢 `GET /api/job-status/{job_id}` 取得進度，不再等待單次長連線
   - **即時狀態資訊 (`job-status`)**：
     - `status`：`running/success/error`
     - `stage`：目前階段（初始化、Parser、合併、Cleaner、BatchProcessor、完成）
     - `progress`：可讀進度文字
     - `current_file`、`parsed_files`、`total_files`：多檔案進度
     - `progress_log`：即時日誌（最多保留 200 筆）
   - **批次處理**：支援選擇**多個 CSV 檔案**或**整個資料夾**，會過濾非 CSV 檔案，逐檔解析後以 `pl.concat(..., how="diagonal_relaxed")` 合併。為避免多檔型別推斷差異，整數欄位會在合併前轉為 `Float64`（`timestamp` 除外）。

## 🚀 3. 啟動與使用方式 (Setup & Usage)

**[啟動後端伺服器]**
請在專案根目錄 (例如 `D:\12.任務\HVAC-1`) 啟動終端機，執行以下指令：

```bash
uvicorn tools.demo.test_server:app --reload --port 8000 --host 0.0.0.0
```

*(註：Windows 環境已內建對應的 `msvcrt` 以取代 `fcntl`，防止跨平台崩潰)*

> **💡 提示**: 使用 `--host 0.0.0.0` 可確保前端透過 `localhost:8000` 或 `127.0.0.1:8000` 都能正確連線。

**[操作前台]**
伺服器啟動後，請直接用瀏覽器開啟 `tools/demo/tester.html` 檔案。

---

## 🔧 4. 階段性診斷工具 (Diagnostic Tools)

診斷工具已**整合至 Step 4**！當 Step 4 (ETL Pipeline) 執行失敗時，診斷區塊會自動顯示在錯誤訊息下方。

### 使用情境

- Step 4 出現 `E202`/`E350`/`E500` 等錯誤碼時
- 需要獨立測試 Parser/Cleaner/BatchProcessor 時
- 開發除錯或問題排查時

### 診斷流程建議

當 Step 4 執行失敗時，診斷區塊會自動顯示，建議按以下順序執行：

```
1️⃣ Parser → 2️⃣ Cleaner → 3️⃣ BatchProcessor → 🔍 Full
```

若 Step 4 一次選了多個 CSV，診斷區塊可先從下拉選單挑選特定檔案，再執行診斷端點。

### 診斷按鈕說明

| 按鈕 | API 端點 | 測試範圍 | 用途 |
|------|----------|----------|------|
| **1️⃣ 測試 Parser** | `POST /api/diagnostic/parser` | Parser 獨立 | 驗證 CSV 解析、編碼偵測、時區轉換 |
| **2️⃣ Parser + Cleaner** | `POST /api/diagnostic/cleaner` | Parser → Cleaner | 驗證資料清洗、品質標記、物理限制檢查 |
| **3️⃣ 到 BatchProcessor** | `POST /api/diagnostic/batch-processor` | 完整 ETL | 驗證批次處理、Manifest 生成、Parquet 輸出 |
| **🔍 完整 ETLContainer** | `POST /api/diagnostic/full` | ETLContainer | 驗證初始化流程、配置載入、Annotation 整合 |

### 診斷結果解析

診斷工具會回傳以下資訊：

- **執行階段**: 顯示每個階段的執行狀態 (ok/error)
- **處理行數**: 每個階段的輸入/輸出行數
- **錯誤詳情**: 完整的錯誤訊息、類型、堆疊追蹤
- **品質標記**: 若為 Cleaner 階段，顯示產生的 quality_flags 樣本

### 常見問題排查

| 診斷結果 | 可能原因 | 解決方案 |
|----------|----------|----------|
| Parser 失敗 | CSV 格式錯誤、編碼問題、缺少時間戳欄位 | 檢查 CSV 標頭、確認包含 Date/Time 或 timestamp 欄位 |
| Cleaner 失敗 | `the truth value of a Series is ambiguous` | 已於 v1.3.0 修復，請更新程式碼 |
| Cleaner E202 | 品質標記不在 VALID_QUALITY_FLAGS 中 | 確認 `config_models.py` 包含所有必要的 flags |
| BatchProcessor 失敗 | `process()` 方法不存在 | 已於 v1.3.0 修復，改為使用 `process_dataframe()` |
| Full 測試失敗 | ETLContainer 初始化失敗 | 檢查 site_id 對應的 YAML 檔案是否存在 |

### UI 行為

- **Step 4 執行中**: 顯示載入動畫
- **Step 4 執行中（新）**: 顯示「即時執行日誌 (Live)」與「即時狀態」面板，回饋目前階段、目前檔案與處理進度
- **Step 4 成功**: 隱藏診斷區塊，顯示結果圖表
- **Step 4 失敗**: 顯示錯誤訊息，並**自動展開診斷區塊**
- **診斷執行中**: 顯示「⏳ 診斷中...」
- **診斷完成**: 在診斷區塊內顯示詳細結果

---

## 📊 5. 快速測試資料說明 (Quick Test Data Guide)

### CSV 格式要求

測試工具支援任何包含欄位標頭（Header）的 CSV 檔案。為確保最佳體驗，建議您的 CSV 包含以下要素：

| 欄位類型 | 說明 | 範例 |
|---------|------|------|
| `timestamp` | 時間戳記欄位（必要） | `2024-01-01 08:00:00`, `2024/01/01 08:00` |
| 數值欄位 | 感測器讀數（溫度、壓力等） | `23.5`, `101.3` |
| 設備標識 | 設備名稱或 ID | `AHU_01`, `CHWP_02` |

### 推薦測試資料來源

專案已內建多組測試 CSV，位於 `tests/fixtures/` 目錄下：

```
tests/fixtures/
├── sample_hvac_data.csv      # 基本 HVAC 測試資料
├── sample_with_errors.csv    # 包含錯誤資料的測試檔
└── sample_large_dataset.csv  # 較大資料量測試
```

**快速開始四步驟**：

1. **Step 1 - 解析預覽**：指定 Parser 類型（或自動偵測），上傳 CSV 預覽解析結果
2. **Step 2 - 產生範本**：點擊「從預覽結果產生 Excel 範本」，系統自動使用 Step 1 的解析結果產生 Excel
3. **Step 3 - 轉換 YAML**：填寫 Excel 標註資訊後上傳，轉換為 YAML 配置檔
4. **Step 4 - ETL 執行**：上傳 CSV 執行完整 ETL 管線（使用與 Step 1 相同的 Parser），查看清洗結果與 E350 違規檢測

**重要提示**：

- Step 1 和 Step 4 使用**相同 Parser**，確保欄位名稱一致性
- Step 2 預設使用 Step 1 的預覽結果，避免重複解析造成的欄位名稱差異
- Excel `column_name` 欄位顯示的是 Parser 標準化後的 snake_case 名稱（如 `ahwp_3_kwh`），與 Step 4 ETL Pipeline 使用的欄位名稱完全一致

---

## 🖥️ 6. 測試 UI 修改評估與規劃 (Phase 0.3 / v1.4 拓樸支援)

因應 `Phase 0.3: v1.4 Retrofit` 將 GNN 拓樸設定（`topology_node_id`, `control_semantic`, `decay_factor` 等）正式貫通於 Clean 與 BatchProcessor，為了提供完善的人工測試體驗，建議對現有的 UI (`tester.html` 與後端 API) 進行以下修改，讓測試人員能夠直觀確認拓樸結果是否正確。

### 工時預估總覽

| 任務 ID | 任務描述 | 預估工時 | 優先級 | 驗收標準 |
|:---:|:---|:---:|:---:|:---|
| UI-001 | Step 4 拓樸摘要面板 | 0.5 天 | 🟡 Medium | 正確顯示節點/邊緣統計、拓樸視覺化 |
| UI-002 | Step 2/3 v1.4 視覺提示 | 0.3 天 | 🟢 Low | 顯示 v1.4 支援提示、欄位說明 |
| UI-003 | 診斷工具 `has_topology` 旗標 | 0.5 天 | 🟡 Medium | API 回傳含拓樸摘要、前端獨立顯示 |
| UI-004 | Excel 範本拓樸欄位提示 | 0.3 天 | 🟢 Low | 下載時顯示拓樸欄位說明 |
| **總計** | | **1.6 天** | | |

### 1. Step 4: 批次結果新增「拓樸上下文 (Topology Context)」區塊

- **現狀**：Step 4 執行完成後，僅將整個 Manifest 以 JSON 格式印在畫面上，無法在第一時間確認新匯入的拓樸結構。
- **UI 修改建議**：
  - 更新標題，標示為支援 v1.4 規格的 Manifest。
  - 在目前的 Manifest 結果區塊的旁邊或下方，**新增一個獨立的面板「🕸️ GNN 拓樸摘要」**。
  - **邏輯實作**：在 `runPipeline()` 成功後的 Javascript 處理區塊中，檢查 `data.result.manifest.topology_context`；若該物件存在且有資料，在前端渲染出該圖結構的摘要資訊。

#### 拓樸資料結構範例

```javascript
// Manifest 中的 topology_context 結構
topology_context: {
  nodes: [
    { id: "chiller_01", type: "chiller", features: ["temp_out", "power_kw"] },
    { id: "chiller_02", type: "chiller", features: ["temp_out", "power_kw"] },
    { id: "pump_01", type: "chiller_pump", features: ["flow_rate", "speed"] },
    { id: "pump_02", type: "chiller_pump", features: ["flow_rate", "speed"] },
    { id: "ahu_01", type: "ahu", features: ["supply_temp", "return_temp"] }
  ],
  edges: [
    { source: "chiller_01", target: "pump_01", relation: "feeds" },
    { source: "chiller_02", target: "pump_02", relation: "feeds" },
    { source: "pump_01", target: "ahu_01", relation: "supplies" },
    { source: "pump_02", target: "ahu_01", relation: "supplies" }
  ],
  adjacency_matrix_shape: [5, 5],  // 節點數 × 節點數
  control_semantic_fields: ["decay_factor", "response_time", "thermal_mass"]
}
```

#### 建議 UI 元素

| 元素 | 說明 | 實作方式 |
|------|------|----------|
| **節點類型統計** | 依設備類型分組計數 | `Chiller: 2, Chiller Pump: 2, AHU: 1` |
| **邊緣關係預覽** | 顯示前 5 條邊 | `chiller_01 → pump_01 (feeds)` |
| **矩陣維度** | 鄰接矩陣大小 | `Adjacency Matrix: 5×5` |
| **控制語義欄位** | Decay factor 等欄位數量 | `Control Semantic: 3 fields` |
| **簡易拓樸圖** | Mermaid.js 流程圖 | 使用 `graph LR` 語法動態生成 |

---

### 2. Step 2 / Step 3: UI 視覺提示升級

- **現狀**：缺乏對 v1.4 特性的提示。
- **UI 修改建議**：
  - **Step 2 Excel 生成後**：顯示提示「📋 此範本支援 v1.4 拓樸註記 (topology_node_id, control_semantic, decay_factor)」
  - **欄位說明提示**：滑鼠 hover 在 Excel 欄位上時顯示說明：
    - `topology_node_id`: 「設備在拓樸圖中的唯一識別碼，用於 GNN 節點對應」
    - `control_semantic`: 「控制語義類型，如 valve/damper/setpoint」
    - `decay_factor`: 「熱慣性衰減係數，用於動態響應建模」
  - **Step 3 YAML 轉換成功後**：顯示確認訊息「✅ YAML 已包含拓樸設定，可供 GNN 模型使用」

---

### 3. Diagnostic 工具 (診斷區塊) 的強化

- **現狀**：`/api/diagnostic/batch-processor` 等診斷 API 目前會印出完整的 Metadata，但未標明是否成功乘載 Topology。
- **後端端點修改建議**：
  - 在 `diagnostic_cleaner` 與 `diagnostic_batch_processor` 的回傳負載中，主動檢查並附加 `topology_summary` 屬性。

#### 建議 API 回傳格式

```python
# diagnostic_cleaner 與 diagnostic_batch_processor 回傳
{
  "status": "success",
  "stages": {
    "parser": {"status": "ok", "rows_in": 1000, "rows_out": 1000},
    "cleaner": {"status": "ok", "rows_in": 1000, "rows_out": 998},
    "batch_processor": {"status": "ok", "parquet_path": "..."}
  },
  "topology_summary": {           # ✅ 新增欄位
    "has_topology": true,         # 是否有拓樸資料
    "node_count": 5,              # 節點數量
    "edge_count": 4,              # 邊緣數量
    "node_types": {               # 節點類型分布
      "chiller": 2,
      "chiller_pump": 2,
      "ahu": 1
    },
    "control_semantic_fields": 3,  # control_semantic 欄位數
    "sample_nodes": [              # 節點預覽（前 3 個）
      {"id": "chiller_01", "type": "chiller"},
      {"id": "pump_01", "type": "chiller_pump"},
      {"id": "ahu_01", "type": "ahu"}
    ]
  },
  "errors": [],
  "quality_flags_sample": []
}
```

- **前端顯示建議**：
  - 在診斷結果區塊新增「🕸️ 拓樸檢測」獨立區域
  - 顯示 `has_topology: ✅ 已載入` 或 `has_topology: ⚠️ 未檢測到`
  - 展開顯示節點數、邊緣數、設備類型分布

---

### 4. Step 2: Excel 範本拓樸欄位提示強化

- **現狀**：測試人員可能不知道新產生的 Excel 包含哪些拓樸相關欄位。
- **UI 修改建議**：
  - **下載按鈕上方**：新增提示區塊：
    ```
    📋 v1.4 Excel 範本包含以下拓樸欄位：
    • topology_node_id - 設備拓樸節點 ID（用於 GNN 圖結構）
    • control_semantic - 控制語義類型（valve/damper/setpoint）
    • decay_factor - 熱慣性衰減係數（0.0-1.0）
    ```
  - **Excel 欄位標頭**：使用下拉選單或資料驗證，限制輸入值（如 control_semantic 只能是預定義值）
  - **填寫範例**：在 Excel 的第一行提供填寫範例，方便測試人員參考

---

### 執行時機與相依性

| 項目 | 說明 |
|------|------|
| **建議執行時機** | ✅ 已完成（2026-03-02）|
| **原因** | 確保拓樸資料流已貫通，UI 可正確顯示實際資料 |
| **前置相依** | ✅ P-R01 (Parser 契約對齊)、C-R01 (Cleaner 邏輯增強)、BP-R01 (BatchProcessor 無損寫入) |
| **相關文件** | `docs/專案任務排程/專案任務排程文件.md` Phase 0.3 區段 |

---

### 執行指示

進行測試工具的版面修改時，請研發人員依據上述四點規劃，修改以下檔案：

1. **`tools/demo/tester.html`** ✅ 已完成
   - ✅ 新增「🕸️ GNN 拓樸摘要」面板（Step 4 結果區）
   - ✅ 新增 v1.4 提示區塊（Step 2 下載區）
   - ✅ 新增診斷結果拓樸摘要顯示

2. **`tools/demo/test_server.py`** ✅ 已完成
   - ✅ 修改 `/api/diagnostic/cleaner` 回傳格式，加入 `topology_summary`
   - ✅ 修改 `/api/diagnostic/batch-processor` 回傳格式，加入 `topology_summary`
   - ✅ 從 Cleaner/BatchProcessor 輸出中提取拓樸資訊

3. **測試驗證項目** ✅ 已實作
   - [x] Step 4 成功後正確顯示節點/邊緣數量
   - [x] 診斷工具正確標示 `has_topology` 狀態
   - [x] Step 2 Excel 下載時顯示 v1.4 提示
   - [x] 拓樸欄位說明文字正確顯示

---

### 實作版本

- **版本號**: v1.6.0
- **實作日期**: 2026-03-02
- **變更檔案**:
  - `tools/demo/tester.html` (新增 `renderTopologySummary()` 函數、拓樸面板 UI)
  - `tools/demo/test_server.py` (診斷 API 新增 `topology_summary` 回傳)
- **Changelog**: 參見本文第 7 節 [v1.6.0] 項目

---

## 📝 7. 改版與問題追蹤紀錄 (Changelog & Issue Tracking)

> **紀錄規範 (Skill 套用: `changelog-writer` & `documentation-templates`)**
> 未來若針對此測試工具有任何修改（包含 UI 更動、後端 API 更新、或發生 Bug修復），請依照 [Semantic Versioning](https://semver.org/) 手動或透過 AI 紀錄於此處。

### [v1.6.0] - 2026-03-02

#### 新增 (Added)

- **v1.4 拓樸支援完整實作** (對應 Phase 0.3 Retrofit):
  - **Step 4 GNN 拓樸摘要面板**: 新增「🕸️ GNN 拓樸摘要」獨立面板，顯示節點數、邊緣數、鄰接矩陣維度、節點類型分布
  - **拓樸視覺化**: 顯示節點預覽（前 5 個）、邊緣預覽（前 3 條）、Control Semantic 欄位列表
  - **Step 2/3 v1.4 提示**: Excel 下載區新增 v1.4 拓樸欄位說明（topology_node_id, control_semantic, decay_factor）

- **診斷工具拓樸檢測強化**:
  - `/api/diagnostic/cleaner` 回傳新增 `topology_summary` 欄位，包含 `has_topology`, `node_count`, `present_columns`, `sample_nodes`
  - `/api/diagnostic/batch-processor` 回傳新增 `topology_summary`，額外包含 Manifest 中的 `topology_context` 資訊
  - 前端診斷結果顯示「🕸️ 拓樸檢測」獨立區塊，標示拓樸資料載入狀態

#### 技術實作 (Technical)

- **後端變更** (`test_server.py`):
  - `diagnostic_cleaner`: 檢查 DataFrame 中的 `topology_node_id`, `control_semantic`, `decay_factor` 欄位，統計節點數與控制語義類型
  - `diagnostic_batch_processor`: 額外讀取 Manifest 中的 `topology_context`，回傳節點/邊緣數量與鄰接矩陣維度

- **前端變更** (`tester.html`):
  - 新增 `renderTopologySummary()` 函數，負責渲染拓樸資訊面板
  - Step 4 結果區改為 Manifest 與拓樸摘要並排布局（grid-2）
  - 診斷結果渲染邏輯新增拓樸摘要顯示

#### PRD 合規性

- ✅ 符合 `PRD_Interface_Contract_v1.2` Phase 0.3 拓樸貫通要求
- ✅ 實作文件第 6 節「測試 UI 修改評估與規劃」所有項目（UI-001 ~ UI-004）
- ✅ 與 `docs/專案任務排程/專案任務排程文件.md` Phase 0.3 完成狀態同步

---

### [v1.3.1] - 2026-02-24

#### 新增 (Added)

- **非同步任務與進度輪詢**:
  - `test_server.py` 將 Pipeline 執行改為背景任務 (`BackgroundTasks`)，避免一次處理大量檔案 (如 200+ 個 CSV) 時造成 HTTP 連線 Timeout (AbortError)。
  - 新增 `/api/job-status/{job_id}` 端點供前端輪詢背景任務狀況。
  - `tester.html` 加入即時進度狀態顯示，可清晰看到如「正在解析檔案 (10/214)」、「執行 Clean...」等步驟回饋。

#### 修復 (Fixed)

- **多檔案處理遺漏**: 修復先前雖然可選取多個檔案，但後端只有針對 `csv_paths[0]` 進行執行的問題。現在會透過 `pl.concat(..., how="diagonal_relaxed")` 自動合併所有上傳的資料。

### [v1.5.0] - 2026-02-25

#### 新增 (Added)

- **Step 1 → Step 2 無縫整合**：
  - **預設流程**：Step 2 現在預設使用「從 Step 1 預覽結果產生」模式，無需重新上傳 CSV
  - **新 API 端點**：`POST /api/generate-template-from-preview` - 直接使用 Step 1 的 Parser 輸出產生 Excel
  - **Wizard 增強**：新增 `run_from_parser_result()` 方法，接收 `columns` 和 `point_mapping` 直接產生 Excel
  - **UI 提示**：Step 1 預覽成功後顯示「✅ 已就緒！解析了 N 個欄位，建議選擇『從 Step 1 預覽結果產生』」

#### 改善 (Improved)

- **欄位名稱一致性**：
  - Excel `column_name` 現在顯示 Parser 標準化後的 snake_case 名稱（如 `ahwp_3_kwh`）
  - 原始監控點名稱（如 `AHWP-3.KWH`）保留在 `description` 欄位，格式：`[Point_X | 原始名稱: AHWP-3.KWH]`
  - 確保 Step 2 產生的 Excel 與 Step 4 ETL Pipeline 使用的欄位名稱完全一致，避免 E409 錯誤

#### PRD 合規性

- ✅ 符合 PRD_Feature_Annotation_Specification_V1.3 第 7.1.1 節（Wizard 與 Parser V2.2 整合）
- ✅ 符合 PRD_Interface_Contract_v1.1 第 10 章（Header Standardization）
- ✅ 未違反 PRD_Wizard_Technical_Blockade_V1.0（Wizard 仍只寫 Excel，不直接寫 YAML）

### [v1.4.0] - 2026-02-25

#### 新增 (Added)

- **Parser V2.2 模組化架構整合**:
  - **Step 1 重構**：新增 Parser 選擇流程，支援手動選擇 Parser 類型（通用 / Siemens Scheduler / 自動偵測）
  - **新 API 端點**：
    - `GET /api/v1/parser/strategies` - 列出可用 Parser 類型
    - `POST /api/v1/pipeline/parse-preview` - 預覽解析結果（含欄位列表、點位映射）
  - **點位映射預覽**：Siemens 格式顯示 Point_N → 設備名稱對照表（如 Point_1: AHWP-3.KWH → ahwp_3_kwh）
  - **命名標準化確認**：顯示原始欄位名稱 → snake_case 轉換後的名稱對照

#### 變更 (Changed)

- **流程調整**：原本的 Step 1 改為 Step 2，新增 Parser 選擇作為 Step 1
- **Wizard 整合**：`wizard_update_excel_with_parser()` 函數支援接收 Parser 輸出，使用已標準化的欄位名稱

### [v1.3.2] - 2026-02-25

#### 新增 (Added)

- **Step 3 即時監控資訊擴充**:
  - 前端新增「🖥️ 即時執行日誌 (Live)」與「📌 即時狀態」區塊，顯示背景任務各階段進度。
  - `job-status` 顯示 `stage/current_file/parsed_files/total_files/progress/progress_log` 等欄位，能即時追蹤多檔案處理狀態。
- **Step 3 失敗後的診斷檔案選擇**:
  - 當一次上傳多檔時，診斷工具新增檔案下拉選單，可指定單一目標檔案進行 Parser/Cleaner/BatchProcessor/Full 診斷。
- **診斷端點支援重採樣參數**:
  - Step 3 診斷流程會帶入 `resample_interval`，讓診斷與主流程配置一致。

#### 改善 (Improved)

- **錯誤上下文更完整**:
  - 後端在 Pipeline 失敗時，會在錯誤訊息附上發生階段與檔名，便於快速定位問題檔案。

### [v1.3.0] - 2026-02-24

#### 新增 (Added)

- **階段性診斷工具**: 在 Step 3 與 Step 4 之間新增 **DIAGNOSTIC** 卡片，提供四個獨立診斷端點：
  - `/api/diagnostic/parser` - 僅測試 Parser
  - `/api/diagnostic/cleaner` - 測試 Parser + Cleaner
  - `/api/diagnostic/batch-processor` - 測試完整 Pipeline
  - `/api/diagnostic/full` - 使用 ETLContainer 完整測試
  - 每個診斷端點回傳詳細的階段狀態、錯誤訊息、堆疊追蹤，便於快速定位問題。

#### 修復 (Fixed)

- **Polars Series 真值歧義錯誤**: 修復 `the truth value of a Series is ambiguous` 錯誤，發生在以下檔案：
  - `src/etl/cleaner.py` `_validate_quality_flags_column()` 方法
  - `src/etl/batch_processor.py` `_validate_input_contract()` 方法
  - `src/etl/parser.py` `_validate_output_contract()` 方法
  - `tests/test_cleaner_v22.py` 測試程式碼
  - 修復方式：將 `if flags:` 改為 `if flags is not None and len(flags) > 0`
- **Polars Expr 真值歧義錯誤**: 修復 `the truth value of an Expr is ambiguous` 錯誤：
  - `tools/demo/test_server.py` 中的 filter 條件組合
  - 修復方式：使用 `pl.col()` 而非直接使用 Series 進行位元運算
- **Cleaner 返回 tuple 處理**: 修復 `test_server.py` 中只接收 `cleaner.clean()` 返回的第一個值，導致後續使用 tuple 而非 DataFrame 的問題：
  - 錯誤寫法：`df_cleaned = cleaner.clean(df_parsed)`
  - 正確寫法：`df_cleaned, metadata, audit = cleaner.clean(df_parsed)`
- **BatchProcessor 方法名稱**: 修復 `bp.process()` 方法不存在的錯誤：
  - 改為使用 `bp.process_dataframe()` 並正確傳入所有必要參數
- **品質標記缺失**: 在 `src/etl/config_models.py` 的 `VALID_QUALITY_FLAGS` 中添加以下標記：
  - `FROZEN_DATA` - 凍結資料偵測
  - `ZERO_VALUE_EXCESS` - 零值過多
  - `PHYSICAL_LIMIT_VIOLATION` - 物理限制違規
  - `FUTURE_DATA` - 未來資料檢查
  - `TIMEZONE_MISMATCH`, `DST_GAP`, `FORMAT_INVALID`, `ENCODING_ERROR`

### [v1.2.1] - 2026-02-24

#### 新增 (Added)

- **多檔案/資料夾選擇**: Step 3 新增「選擇檔案」、「選擇資料夾」、「清除選擇」功能按鈕，支援：
  - 選擇多個 CSV 檔案 (`multiple` 屬性)
  - 選擇整個資料夾自動過濾 CSV 檔案 (`webkitdirectory` 屬性)
  - 即時顯示已選擇檔案數量
- **後端 API 批次支援**: `/api/run-pipeline` 改為接受 `files: List[UploadFile]`，支援多檔案上傳並自動過濾非 CSV 檔案。

#### 修復 (Fixed)

- **Step 2 site_id 提取錯誤**: 修復 `excel_to_yaml.py` 的 `parse_metadata()` 無法正確從臨時檔案名（如 `321_site_filled.xlsx`）提取 `site_id` 的問題。新增 `_extract_site_id_from_filename()` 方法，支援多種檔案命名格式：
  - `Feature_{site_id}_v1.3.xlsx`
  - `{site_id}_filled.xlsx` (test_server 臨時檔案)
  - `{site_id}_template.xlsx`
  - `{site_id}_features.xlsx`
- **Pydantic 驗證失敗**: 修復因 YAML 缺少 `metadata.site_id` 欄位導致的 `SiteFeatureConfig` 驗證錯誤 (`site_id Field required`)。

### [v1.2.2] - 2026-02-24

#### 新增 (Added)

- **設定清洗與重採樣間隔**: 在 Step 3 UI 中新增了「清洗與重採樣間隔 (Resample Interval)」的下拉選單，允許使用者動態切換聚合時間粒度 (`5m`, `10m`, `15m`, `30m`, `1h`)。後端會自動攔截這個參數並套用至 DataCleaner 的配置中，取代原本寫死的 5 分鐘。

---

### [v1.2.0] - 2026-02-24

#### 新增 (Added)

- **Chaos Testing (防禦機制驗證)**: 在 UI 頂端新增獨立的測試卡片，提供快捷按鈕直接對後端戳送 E000, E406, E500 錯誤碼，驗證 FastApi 層與後端業務邏輯的防護能力。
- **Parquet 檔案下載**: 在 Step 3 執行完畢並展示 Manifest 後，新增「下載 Parquet」按鈕，可直接透過 `/api/download-parquet/{site_id}` 取得由 BatchProcessor 落地的最新整理檔案。
- **Sprint 4~5 預留擴充點**:
  - `tester.html` 追加 Step 5 (最佳化引擎) 與 Step 6 (系統端到端整合) 灰色佔位卡片，當先前步驟符合條件 (`integration_input_ready`) 便會自動解鎖顯示。
  - `test_server.py` 加入對應的空殼路由 `/api/run-optimization` 與 `/api/run-integration` 支援前端按鈕。

### [v1.1.1] - 2026-02-24

#### 新增 (Added)

- **Sprint 3 預留擴充點**:
  - `test_server.py` 新增 `POST /api/run-feature-engineer` 空殼路由，為即將到來的 Sprint 3 預先架設 API。
  - `tester.html` 新增 **Step 4 (Sprint 3)** 隱藏卡片，當 Step 3 清洗完成時會自動展開提示。

#### 修復 (Fixed)

- **FastAPI 單例重複初始化預防**: 在 `test_server.py` 的 `/api/run-pipeline` 中，於 `ETLContainer` 啟動前呼叫 `PipelineContext.reset_for_testing()`，防止多次請求造成 "PipelineContext 已初始化" 的 500 錯誤。
- **UI 錯誤區塊未渲染問題**: 修正 `tester.html` 缺少 `<div id="errorOutput">` 元素導致錯誤發生時無法正常顯示錯誤碼及紅底警告框的 Bug。

### [v1.1.0] - 2026-02-24

#### 新增 (Added)

- **後端健康檢查端點 (`GET /api/health`)**: 回傳伺服器狀態與時間戳記，供前端連線驗證使用。
- **錯誤碼測試端點 (`POST /api/test-error`)**: 支援刻意觸發 E000/E406/E500 錯誤碼，便於驗證防禦機制。
- **前端健康檢查 Banner**: 頁面載入時自動偵測後端連線狀態，顯示 ✅ 連線成功 或 ⚠️ 後端未啟動 提示。
- **複製 JSON 按鈕**: Manifest 與 E350 違規結果框新增「複製 JSON」按鈕，便於資料分析。
- **強化雷達圖數據**: 從硬編碼假值改為動態計算 `nan_inf_rate`, `timezone_error_rate`, `format_error_rate`, `outlier_rate` 五個維度。

#### 修復 (Fixed)

- **修正 `BackgroundTasks` 使用錯誤**: `FileResponse` 的 `background` 參數應使用 `BackgroundTask`（單個）而非 `BackgroundTasks`（列表），避免臨時檔案無法清理造成記憶體洩漏。
- **改善 Step 3 錯誤回饋**: 將 `alert()` 彈窗改為頁面內錯誤訊息框，並高亮顯示錯誤碼（如 E000, E350, E500 等）。

### [v1.0.0] - 2026-02-24

#### 新增 (Added)

- **UI三步互動式介面 (`tester.html`)**: 加入了上傳 CSV 產生 Excel、上傳 Excel 轉 YAML、完整管線執行並繪製圖表 (Chart.js 雷達圖)。
- **FastAPI 測試伺服端 (`test_server.py`)**:
  - `POST /api/generate-template` 串接 Wizard。
  - `POST /api/convert-yaml` 串接 Converter。
  - `POST /api/run-pipeline` 串接 Parser v2.1, Cleaner v2.2, BatchProcessor。

#### 修復 (Fixed)

- 修正 Windows 系統下 `ConfigLoader` 呼叫 `fcntl` 模組導致的致命錯誤 `ModuleNotFoundError`。透過在 `config_loader.py` 中掛載 Windows 專用 `msvcrt.locking` 解決了跨平台檔案鎖被鎖死的問題。

#### 已知問題 (Known Issues)

- **錯誤碼測試路由限制**: 目前 `POST /api/test-error` 端點僅模擬錯誤回應，若要完整驗證 E000 (Cleaner & BatchProcessor 前置條件失敗)、E406 (ConfigLoader 同步檢查)、E500 (輸入契約防護) 的實際觸發情境，仍需直接執行單元測試 `pytest tests/ -v`。
- ~~網頁端在處理超過 500MB 以上超大 CSV 時，可能發生 timeout 斷線，未來可考慮進一步增強非同步進度條回報功能。~~ *(已於 v1.3.1 透過 BackgroundTasks 與前端輪詢實作解決)*
