# 🧪 全域互動式 ETL 測試工具 (Interactive ETL Tester)

## 📖 1. 工具總覽 (Overview)
**目標**：提供一個無需手動輸入終端機指令（Command Line），透過網頁即可完整體驗從資料清洗、特徵標註、設備預檢與批次落地 (Sprint 1~5) 的單一互動式測試平台。
**位置**：
- **後端 API**: `tools/demo/test_server.py` (FastAPI)
- **前端 UI**: `tools/demo/tester.html` (HTML + CSS + JS)

## ⚙️ 2. 架構與功能 (Architecture & Features)
本測試工具總共涵蓋三個主要步驟，模擬真實的案場導入流程：

1. **Step 1: 自動生成 Excel 標註範本 (`/api/generate-template`)**
   - **背後機制**：呼叫 `FeatureAnnotationWizard` (`tools/features/wizard.py`)
   - **功能**：上傳任意原始 CSV，系統自動分析欄位 (Header) 並結合內部演算法，推測出潛在的 HVAC 設備類型，最終產生並下載一份空白但帶有下拉選單與輔助提示的 Excel 檔案。
2. **Step 2: 轉換 Excel 為 YAML SSOT (`/api/convert-yaml`)**
   - **背後機制**：呼叫 `ExcelToYamlConverter` (`tools/features/excel_to_yaml.py`)
   - **功能**：人工填寫完 Excel 後將其上傳，系統會檢查硬性約束 (E400, E403 等錯誤碼) 並產出為單一真相源 (`.yaml`) 檔案至 `config/features/sites/` 下。
3. **Step 3: 執行完整 ETL Pipeline (`/api/run-pipeline`)**
   - **背後機制**：呼叫 `ETLContainer`, `PipelineContext`, `ReportParser`, `DataCleaner` 以及 `BatchProcessor`。
   - **功能**：輸入原始 CSV，系統將讀取 Step 2 產生的 YAML 設定檔。執行編碼偵測、時區校正、語意對應清洗與 E350 設備物理違規檢查，最後由 `BatchProcessor` 將資料落地，並返回清洗圖表、異常條目與 `Manifest v1.3`。
   - **批次處理**：支援選擇**多個 CSV 檔案**或**整個資料夾**，系統會自動過濾並處理所有 CSV 檔案（目前實作為處理第一個檔案，未來版本將支援批次合併處理）。

## 🚀 3. 啟動與使用方式 (Setup & Usage)

**[啟動後端伺服器]**
請在專案根目錄 (例如 `D:\12.任務\HVAC-1`) 啟動終端機，執行以下指令：
```bash
uvicorn tools.demo.test_server:app --reload --port 8000
```
*(註：Windows 環境已內建對應的 `msvcrt` 以取代 `fcntl`，防止跨平台崩潰)*

**[操作前台]**
伺服器啟動後，請直接用瀏覽器開啟 `tools/demo/tester.html` 檔案。

---

## 🔧 4. 階段性診斷工具 (Diagnostic Tools)

診斷工具已**整合至 Step 3**！當 Step 3 (ETL Pipeline) 執行失敗時，診斷區塊會自動顯示在錯誤訊息下方。

### 使用情境
- Step 3 出現 `E202`/`E350`/`E500` 等錯誤碼時
- 需要獨立測試 Parser/Cleaner/BatchProcessor 時
- 開發除錯或問題排查時

### 診斷流程建議
當 Step 3 執行失敗時，診斷區塊會自動顯示，建議按以下順序執行：
```
1️⃣ Parser → 2️⃣ Cleaner → 3️⃣ BatchProcessor → 🔍 Full
```

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

- **Step 3 執行中**: 顯示載入動畫
- **Step 3 成功**: 隱藏診斷區塊，顯示結果圖表
- **Step 3 失敗**: 顯示錯誤訊息，並**自動展開診斷區塊**
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

**快速開始三步驟**：
1. 使用 `tests/fixtures/sample_hvac_data.csv` 作為 Step 1 輸入
2. 在產生的 Excel 中標註 `timestamp` 欄位為時間索引
3. 執行 Step 3 查看清洗效果與 E350 違規檢測

---

## 📝 6. 改版與問題追蹤紀錄 (Changelog & Issue Tracking)

> **紀錄規範 (Skill 套用: `changelog-writer` & `documentation-templates`)**
> 未來若針對此測試工具有任何修改（包含 UI 更動、後端 API 更新、或發生 Bug修復），請依照 [Semantic Versioning](https://semver.org/) 手動或透過 AI 紀錄於此處。

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
- 網頁端在處理超過 500MB 以上超大 CSV 時，可能發生 timeout 斷線，未來可考慮進一步增強非同步進度條回報功能。
