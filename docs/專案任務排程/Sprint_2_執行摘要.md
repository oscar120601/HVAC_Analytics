# Sprint 2 執行摘要

**Sprint 名稱**: 核心 ETL (Core ETL Pipeline)  
**時間範圍**: 第 3-6 週 (2026-02-23 ~ 2026-02-25)  
**狀態**: ✅ **已完成 (4/4 完成，含 Parser v2.2 模組化重構 + Demo ✅ 已交付)**  
**審查狀態**: [📋 Sprint 2 Review Report](./Sprint_2_Review_Report.md) - Parser v2.1 (A級), Cleaner v2.2 (A級), BatchProcessor v1.3 (A-級)；Parser v2.2 模組化驗收完成  
**文件版本**: v1.4  
**建立日期**: 2026-02-23  
**最後更新**: 2026-02-25

---

## 一、Sprint 目標

建立資料攝取、清洗、批次處理流程，確保：
- **嚴格契約驗證**: 所有模組輸出符合 Interface Contract v1.1
- **時間基準傳遞**: PipelineContext 時間基準貫穿整個 ETL 流程
- **零間隙對接**: Parser → Cleaner → BatchProcessor 無縫銜接
- **可視化展示**: 建立 Sprint 2 Demo 展示頁面

## 審查總覽

| 模組 | 版本 | 評分 | 狀態 | 備註 |
|:---|:---:|:---:|:---:|:---|
| Parser | v2.1 | 🟢 **A級** | ✅ 可生產 | 全數通過，無需重工 |
| Parser (模組化) | v2.2 | ✅ **完成** | ✅ 可生產 | Strategy Pattern、Siemens Scheduler、相容層與遷移指南已交付 |
| Cleaner | v2.2 | 🟢 **A級** | ✅ 可生產 | 所有問題全數關閉，具備完整生產級品質 |
| BatchProcessor | v1.3 | 🟡 **A-級** | ✅ 通過 | 4項 Critical/High 修復完成，1項 Medium 待修復 |
| Sprint 2 Demo | - | 🟢 **B+級** | ✅ 已上線 | 5/5 項任務達成，2個低風險項目 |
| **Sprint 2 整體** | - | **A-** | ✅ **完成** | **可進入 Sprint 3** |

---

## 二、任務完成狀態

| 任務 | 版本 | 預估工時 | 實際工時 | 狀態 | 測試 | 審查結果 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| Parser | v2.1 | 4-5天 | 1天 | ✅ **已完成** | 16 案例（已納入 v2.2 回歸） | 🟢 A級 |
| Parser 模組化重構 | v2.2 | 6-8天 | 1天 | ✅ **已完成** | 29 案例（含 v2.1 回歸） | ✅ 驗收通過（覆蓋率 84%） |
| Cleaner | v2.2 | 6-7天 | 1天 | ✅ **已完成** | 26 案例 | 🟢 A級 |
| BatchProcessor | v1.3 | 5-6天 | 1天 | ✅ **已完成** | 32 案例 | ✅ 通過 |
| Sprint 2 Demo | - | 1.5天 | 0.5天 | ✅ **已完成** | - | ✅ 已上線 |

**測試總計**: Parser v2.2（含 v2.1 回歸）(29) + Cleaner (12+14=26) + BatchProcessor (32) = **87 項測試通過**  
**累計測試**: Sprint 1 (53) + Sprint 2 (87) = **140 項測試**

---

## 三、已完成項目詳情

### ✅ 2.1 Parser v2.1 (2026-02-23 完成)

**審查結論**: 🟢 **A級** - 全數通過，無需重工

#### 3.1.1 交付物

| 檔案 | 說明 | 行數 |
|:---|:---|:---:|
| `src/etl/parser.py` | ReportParser v2.1 主實作 | 770+ |
| `src/exceptions.py` | 擴充例外類別 (4 個新類別) | 60+ |
| `config/site_templates.yaml` | 案場配置範本 | 120+ |
| `tests/test_parser_v21.py` | 單元測試 (16 個案例) | 450+ |

#### 3.1.2 核心功能實作

**編碼自動偵測 (P-001~P-002)**
```python
def _detect_encoding(self, file_path: Path) -> str:
    """自動偵測 UTF-8/Big5/UTF-16，處理 BOM"""
    # BOM 優先偵測
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    # 嘗試順序: UTF-8 → CP950 → UTF-16
```

**智慧標頭搜尋 (P-003)**
```python
def _find_header_line(self, file_path: Path, encoding: str) -> int:
    """掃描前 500 行，支援中文標頭 (日期/時間/Date/Time)"""
    # 評分機制: Date+Time (+2分), DateTime (+2分), 欄位數>3 (+1分)
    # 分隔符一致性驗證防止誤判
```

**時區強制轉換 (P-004)**
```python
def _standardize_timezone(self, df: pl.DataFrame) -> pl.DataFrame:
    """強制輸出 Datetime(time_unit='ns', time_zone='UTC')"""
    # 情況1: 已為 UTC → 確認 time_unit
    # 情況2: 其他時區 → convert_time_zone("UTC")
    # 情況3: Naive → replace_time_zone(assumed) → convert_time_zone("UTC")
```

**髒資料清洗 (P-005)**
```python
def _clean_and_cast(self, df: pl.DataFrame) -> pl.DataFrame:
    """處理 BAS 常見髒資料"""
    # "25.3 C" → 25.3 (移除單位)
    # "---", "Error", "N/A" → null
    # "100%" → 100.0
```

**輸出契約驗證 (P-006)**
```python
def _validate_output_contract(self, df: pl.DataFrame) -> None:
    """Interface Contract v1.0 檢查點 #1"""
    # E101: BOM/Null byte 檢查
    # E102: timestamp 必須為 UTC/ns
    # E103: 必要欄位存在性
    # E104/E105: 標頭相關錯誤
```

#### 3.1.3 錯誤代碼實作

| 錯誤碼 | 名稱 | 說明 | 狀態 |
|:---:|:---|:---|:---:|
| E101 | ENCODING_MISMATCH | 編碼無法偵測或 BOM 殘留 | ✅ |
| E102 | TIMEZONE_VIOLATION | 時區非 UTC 或精度錯誤 | ✅ |
| E103 | CONTRACT_VIOLATION | 缺少必要欄位 | ✅ |
| E104 | HEADER_NOT_FOUND | 掃描 500 行無法定位標頭 | ✅ |
| E105 | HEADER_STANDARDIZATION_FAILED | 標頭正規化失敗 | ✅ |

#### 3.1.4 案場配置範本

```yaml
# config/site_templates.yaml
schema_version: "2.1"

default:
  encoding: auto          # auto | utf-8 | cp950 | utf-16
  delimiter: ","
  assumed_timezone: "Asia/Taipei"
  null_values: ["", "NA", "null", "---", "Error", "N/A"]
  column_mapping:
    "日期": "Date"
    "時間": "Time"
    "冰水主機電流": "chiller_current"

cgmh_ty:  # 長庚醫院桃園院區
  inherit: default
  header_prefix: "<>"

farglory_o3:  # 遠雄 O3
  inherit: default
  encoding: cp950
  delimiter: "\t"
```

#### 3.1.5 測試案例

| 測試 ID | 描述 | 驗證項目 |
|:---:|:---|:---|
| P21-001 | UTF-8 BOM 處理 | BOM 偵測與移除 |
| P21-002 | Big5 編碼偵測 | 中文標頭正確解析 |
| P21-003 | 時區轉換 Asia/Taipei → UTC | 時間正確轉換 (-8小時) |
| P21-004 | Naive datetime 假設時區 | assumed_timezone 應用 |
| P21-005 | 時區錯誤攔截 | E102 拋出驗證 |
| P21-006 | 髒資料清洗 | "25.3 C" → 25.3 |
| P21-007 | 標頭分隔符一致性 | 防止中繼資料行誤判 |
| P21-008 | 輸出契約驗證 | E101-E105 驗證 |
| P21-009 | CamelCase 標頭轉換 | ChillerCurrent → chiller_current |
| P21-010 | 中文標頭保留 | 1號冰水主機 → col_1號冰水主機 |
| P21-011 | 標頭正規化唯一性 | 重複欄位偵測 (E105) |
| P21-012 | 整合測試 | Parser → DataFrame 端到端 |

---

### ✅ 2.1.1 Parser v2.2 模組化重構 (2026-02-25 完成)

**驗收結論**: ✅ **完成** - 模組化架構與相容層均已上線，通過回歸與整合測試

#### 3.1.6 交付物

| 檔案 | 說明 |
|:---|:---|
| `src/etl/parser/__init__.py` | `ParserFactory`、`get_parser`、`ReportParser` 相容 facade |
| `src/etl/parser/base.py` | `BaseParser` 抽象類別 |
| `src/etl/parser/generic_parser.py` | `GenericParser`（v2.1 行為相容） |
| `src/etl/parser/siemens/scheduler_report.py` | Siemens Scheduler 解析器 |
| `src/etl/parser/siemens/point_mapping.py` | Siemens 點位映射處理 |
| `src/etl/parser.py` | 舊入口相容 shim（re-export v2.2 API） |
| `tests/parser/test_base.py` | BaseParser 契約測試 |
| `tests/parser/test_factory.py` | Factory / auto_detect 測試 |
| `tests/parser/test_siemens_scheduler.py` | Siemens 格式測試 |
| `tests/parser/test_integration.py` | Parser → Cleaner 整合測試 |
| `docs/parser/MIGRATION_v2.1_to_v2.2.md` | 遷移指南 |

#### 3.1.7 關鍵能力

- Strategy Pattern 解析器策略切換（`generic` / `siemens_scheduler` / `auto`）
- `ParserFactory.auto_detect()` 可辨識 Siemens 格式，未知格式 fallback `generic`
- `ReportParser` 舊呼叫入口維持可用，不破壞既有 v2.1 流程
- 新增 API 端點：`/api/v1/parser/strategies`、`/api/v1/pipeline/parse-preview`

#### 3.1.8 測試與品質門檻

- `pytest -q tests/parser tests/test_parser_v21.py`：29 項測試通過
- `pytest --cov=src.etl.parser`：Parser 模組覆蓋率 **84%**
- Gate 全數通過：E101-E105 一致性、metadata 含 `pipeline_origin_timestamp`、相容層驗證

---

### ✅ 2.2 Cleaner v2.2 (2026-02-23 完成)

**審查結論**: 🟢 **A級** - 所有問題全數關閉，具備完整生產級品質

**改善計畫驗收**: 10/10 項達成 (v2.1)

#### 3.2.1 交付物

| 檔案 | 說明 | 行數 |
|:---|:---|:---:|
| `src/etl/cleaner.py` | DataCleaner v2.2 主實作 | 1303+ |
| `tests/test_cleaner_simple.py` | 基礎單元測試 (12 個案例) | 200+ |
| `tests/test_cleaner_v22.py` | v2.2 功能測試 (10 個案例) | 622+ |
| `tests/test_cleaner_equipment_validation.py` | 設備驗證測試 (14 個案例) | 370+ |

#### 3.2.2 核心功能實作

**Temporal Context 注入 (C-001)**
```python
def __init__(self, ..., pipeline_context: Optional[PipelineContext] = None):
    # E000: 強制檢查 pipeline_context
    if pipeline_context is None:
        raise RuntimeError("E000: DataCleaner 必須接收 PipelineContext")
    self.pipeline_origin_timestamp = pipeline_context.get_baseline()
```

**FeatureAnnotationManager 整合 (C-002)**
```python
# 讀取 device_role 進行語意感知清洗
role = self.annotation.get_device_role(column_name)
# primary: 嚴格閾值
# backup/seasonal: 放寬閾值
```

**未來資料檢查 (C-004)** - 強化版
```python
def _check_future_data(self, df: pl.DataFrame) -> pl.DataFrame:
    """使用 pipeline_origin_timestamp 檢查，非 datetime.now()"""
    # 容忍 5 分鐘誤差
    # 新增 future_data_behavior: "reject"(default) | "filter" | "flag_only"
```

**設備邏輯預檢 (C-006)** - SSOT 驅動
```python
def _apply_equipment_validation_precheck(self, df: pl.DataFrame):
    """E350: 設備邏輯預檢 - SSOT 分派表驅動"""
    # _CONSTRAINT_HANDLERS 分派表：
    # - chiller_pump_mutex: 主機開啟時水泵必須運轉
    # - pump_redundancy: 至少一台冷凍水泵和冷卻水泵運轉
    # 違規標記: PHYSICAL_IMPOSSIBLE
    # PRECHECK_CONSTRAINTS 鍵集動態決定執行哪些 handler
```

**Schema 淨化 - E500 防護 (C-008)**
```python
FORBIDDEN_COLS = frozenset({
    'device_role', 'ignore_warnings', 'is_target', 'role',
    'device_type', 'annotation_role', 'col_role', 'feature_role'
})
# 輸出前強制移除
```

**quality_flags 重採樣邏輯 (C-007)** - 已修正
```python
# explode().unique().implode() 確保 flags 正確合併
```

#### 3.2.3 錯誤代碼實作

| 錯誤碼 | 名稱 | 說明 | 狀態 |
|:---:|:---|:---|:---:|
| E000 | TEMPORAL_BASELINE_MISSING | 未提供 PipelineContext | ✅ |
| E102 | FUTURE_DATA_DETECTED | 資料時間超過 pipeline_origin_timestamp | ✅ (強化) |
| E350 | EQUIPMENT_LOGIC_PRECHECK_FAILED | 設備邏輯違規 | ✅ (SSOT驅動) |
| E500 | DEVICE_ROLE_LEAKAGE | device_role 洩漏到輸出 | ✅ |

#### 3.2.4 改善計畫驗收摘要

| 項目 | 改善內容 | 驗收結果 |
|:---:|:---|:---:|
| Phase 1-1 | quality_flags 重採樣邏輯 | ✅ 通過 |
| Phase 1-2 | future_data_behavior 3種模式 | ✅ 通過 |
| Phase 1-3 | test_c22_ts_03 永真斷言修正 | ✅ 通過 |
| Phase 1-4 | 新增設備驗證測試檔 | ✅ 通過 (370行) |
| Phase 2-1 | EQUIPMENT_TYPE_PATTERNS 集中管理 | ✅ 通過 |
| Phase 2-2 | 稽核軌跡時間語意區分 | ✅ 通過 |
| Phase 2-3 | 凍結偵測邊界防護 | ✅ 通過 |
| Phase 3-1 | _is_snake_case 中文前綴支援 | ✅ 通過 |
| Phase 3-2 | 測試隔離性 (reset_for_testing) | ✅ 通過 |
| Phase 3-3 | PRECHECK_CONSTRAINTS SSOT 驅動 | ✅ 通過 |

#### 3.2.5 測試案例

**基礎測試 (test_cleaner_simple.py)**

| 測試 ID | 描述 | 驗證項目 |
|:---:|:---|:---|
| C22-001 | E000 缺失 temporal context | RuntimeError 拋出 |
| C22-002 | SSOT 品質標記載入 | 20 flags 驗證 |
| C22-003 | SSOT 設備約束載入 | 6 constraints 驗證 |
| C22-004 | 禁止欄位清單 | 8 columns 驗證 |
| C22-005 | Cleaner 正確初始化 | pipeline_context 注入 |
| C22-006 | Temporal baseline 儲存 | 時間基準正確保存 |
| C22-007 | MockContext 時間行為 | is_future 檢測 |
| C22-008 | 設備互斥約束結構 | chiller_pump_mutex |
| C22-009 | 泵浦冗餘約束結構 | pump_redundancy |
| C22-010 | 品質標記完整性 | 必要 flags 存在 |

**設備驗證測試 (test_cleaner_equipment_validation.py)**

| 測試類別 | 案例數 | 說明 |
|:---|:---:|:---|
| TestChillerPumpMutex | 3 | 主機水泵互斥檢測 |
| TestPumpRedundancy | 2 | 泵浦冗餘檢測 |
| TestMultiChillerScenarios | 2 | 多主機場景 |
| TestAuditTrail | 3 | 稽核軌跡結構與時間驗證 |
| TestEquipmentColumnDetection | 2 | 命名模式識別 |
| TestEdgeCases | 2 | 邊界條件 |

---

### ✅ 2.3 BatchProcessor v1.3 (2026-02-24 完成)

**審查結論**: 🟢 **A-級** - 4項 Critical/High 問題已修復，1項 Medium 新問題待 Sprint 3 前修復

**任務驗收**: 10/10 項達成（E000, E205, E500, E351, E202, E206, E406, E408, Manifest, 事務性輸出）

#### 3.3.1 交付物

| 檔案 | 說明 | 行數 |
|:---|:---|:---:|
| `src/etl/batch_processor.py` | BatchProcessor v1.3 主實作 | 810+ |
| `src/etl/manifest.py` | Manifest 生成器 v1.3-CA | 250+ |
| `tests/test_batch_processor_v13.py` | 單元測試 (32 個案例) | 600+ |

#### 3.3.2 核心功能實作

**Temporal Context 注入**
```python
def __init__(self, ..., pipeline_context: Optional[PipelineContext] = None):
    # E000: 強制檢查 pipeline_context
    if pipeline_context is None:
        raise RuntimeError("E000: BatchProcessor 必須接收 PipelineContext")
    self.pipeline_origin_timestamp = pipeline_context.get_baseline()
```

**輸入契約驗證 (E500/E202/E205)**
```python
def _validate_input_contract(self, df: pl.DataFrame) -> None:
    """檢查輸入資料符合 Cleaner 輸出契約"""
    # E500: 禁止欄位檢查 (device_role 等)
    # E202: 時區必須為 UTC
    # E205: 欄位名稱必須為 snake_case
```

**Parquet 寫入 (INT64/UTC)**
```python
def _write_parquet(self, df: pl.DataFrame, output_path: Path) -> None:
    """強制型別: timestamp → UTC/ns, 數值 → INT64"""
    # 確保下游 Spark/Feast 相容性
    # 使用 polars.write_parquet  with use_pyarrow=True
```

**Manifest 生成 v1.3-CA**
```python
def _generate_manifest(self, df: pl.DataFrame, output_path: Path) -> Dict:
    """生成符合 Contract v1.1 的 Manifest"""
    # schema_version: "1.3-CA"
    # temporal_range: {start, end, baseline}
    # quality_summary: 統計資訊
    # equipment_audit_trail: 設備驗證稽核軌跡
```

**E408 SSOT 版本檢查**
```python
def _validate_ssot_versions(self) -> None:
    """檢查 SSOT 配置版本相容性"""
    # 讀取 quality_flags.yaml 和 equipment_constraints.yaml
    # 驗證 schema_version 符合預期
    # E408: SSOT_VERSION_MISMATCH
```

**事務性輸出**
```python
def process(self, df: pl.DataFrame, output_dir: Path) -> BatchResult:
    """原子性寫入: 臨時目錄 → 驗證 → 重新命名"""
    # 確保輸出完整性，避免部分寫入
    # 失敗時清理臨時檔案
```

#### 3.3.3 錯誤代碼實作

| 錯誤碼 | 名稱 | 說明 | 狀態 |
|:---:|:---|:---|:---:|
| E000 | TEMPORAL_BASELINE_MISSING | 未提供 PipelineContext | ✅ |
| E202 | TIMEZONE_VIOLATION | 時區非 UTC | ✅ |
| E205 | SCHEMA_VIOLATION | 欄位名稱不符合 snake_case | ✅ |
| E206 | PARQUET_WRITE_ERROR | Parquet 寫入失敗 | ✅ |
| E351 | DEVICE_ROLE_LEAKAGE | device_role 洩漏到輸入 | ✅ |
| E406 | MANIFEST_GENERATION_ERROR | Manifest 生成失敗 | ✅ |
| E408 | SSOT_VERSION_MISMATCH | SSOT 配置版本不符 | ✅ |
| E500 | INPUT_CONTRACT_VIOLATION | 輸入契約違反 | ✅ |

#### 3.3.4 測試案例 (32 項)

| 測試類別 | 案例數 | 說明 |
|:---|:---:|:---|
| TemporalContext | 3 | PipelineContext 注入與時間基準 |
| InputContract | 6 | E500/E201/E202/E205 驗證（+E201 型別驗證） |
| ParquetOutput | 4 | INT64/UTC 強制轉換 |
| Manifest | 4 | v1.3-CA Manifest 生成 |
| SSOTVersion | 2 | E408 版本檢查 |
| Transaction | 3 | 事務性輸出與失敗清理 |
| Integration | 6 | 端到端流程測試 |
| FutureData | 2 | E205 未來資料檢測 |
| TimeConsistency | 1 | 多次處理基準不變 |

**測試統計**: v3.0: 29 項 → v4.0: **32 項**（+E201 型別驗證測試，+E408 SSOT 驗證測試）

---

### ✅ 2.4 Sprint 2 Demo 展示 (2026-02-24 完成)

#### 3.4.1 交付物

| 檔案 | 說明 | 大小 |
|:---|:---|:---:|
| `tools/demo/sprint2_etl.html` | Demo 主頁面 (深色主題) | 48KB |
| `tools/demo/data/sprint2_etl_sample.json` | 範例資料 | 12KB |

#### 3.4.2 完成任務

**5 項任務全部完成**: DEMO-201 ~ DEMO-205

| 任務 ID | 內容 | 狀態 |
|:---:|:---|:---:|
| DEMO-201 | ETL 三階段流程動畫 | ✅ |
| DEMO-202 | 品質指標雷達圖 | ✅ |
| DEMO-203 | 設備邏輯違規案例展示 | ✅ |
| DEMO-204 | 深色主題 UI 設計 | ✅ |
| DEMO-205 | 響應式佈局 | ✅ |

#### 3.4.3 頁面特色

- **深色主題**: 現代化暗色介面，適合演示環境
- **雷達圖**: 多維度品質指標視覺化
- **ETL 流程動畫**: Parser → Cleaner → BatchProcessor 流程展示
- **設備驗證展示**: 互動式設備邏輯檢測結果

#### 3.4.4 開啟方式

```bash
cd tools/demo
python -m http.server 8080
# 瀏覽器開啟 http://localhost:8080/sprint2_etl.html
```

---

## 四、進行中項目

Sprint 2 已全部完成，無進行中項目。

---

## 五、技術決策記錄

### 5.1 Parser 編碼偵測順序

**決策**: UTF-8 → CP950 → UTF-16  
**理由**: 
- 台灣 BAS 系統多數已支援 UTF-8
- Big5 (CP950) 為舊系統相容
- UTF-16 為特殊案例

### 5.2 時區處理策略

**決策**: 無時區資料假設為 Asia/Taipei  
**理由**:
- 台灣案場為主要使用場景
- `site_templates.yaml` 可配置 `assumed_timezone`
- 未來擴展國際案場只需修改配置

### 5.3 Cleaner SSOT 設備約束驅動

**決策**: `_CONSTRAINT_HANDLERS` 分派表由 `PRECHECK_CONSTRAINTS` 鍵集動態驅動  
**理由**:
- 新增 constraint 只需修改配置，無需修改流程主體
- 符合 SSOT 原則
- 便於 HVAC 領域專家調整約束條件

### 5.4 標頭搜尋範圍

**決策**: 限制 500 行  
**理由**:
- 平衡效能與準確性
- 絕大多數 BAS 報表標頭在前 100 行內
- 超大檔案不會無限掃描

### 5.5 BatchProcessor 事務性輸出

**決策**: 臨時目錄 → 驗證 → 重新命名  
**理由**:
- 確保輸出原子性
- 避免部分寫入導致資料損壞
- 失敗時可安全清理

### 5.6 Manifest 版本命名

**決策**: v1.3-CA (Cleaner-Aware)  
**理由**:
- 明確標示與 Cleaner v2.2 的整合
- 包含 equipment_audit_trail 欄位
- 向下相容性考量

---

## 六、Sprint 2 完成摘要

### 6.1 完成概覽

| 模組 | 版本 | 測試數 | 狀態 |
|:---|:---:|:---:|:---:|
| Parser (含模組化) | v2.2 | 29 | ✅ 完成（含 v2.1 回歸） |
| Cleaner | v2.2 | 26 | ✅ A級 |
| BatchProcessor | v1.3 | 32 | ✅ 通過 |
| **總計** | - | **87** | **✅ 全部通過** |

### 6.2 測試統計

- **新增測試**: 87 項（Parser 29 + Cleaner 26 + BatchProcessor 32）
- **累計測試**: 140 項 (Sprint 1: 53 + Sprint 2: 87)
- **測試覆蓋**: Parser + Cleaner + BatchProcessor 端到端流程

### 6.3 Demo 上線

- **Demo 頁面**: `tools/demo/sprint2_etl.html`
- **訪問方式**: `python -m http.server 8080`
- **展示內容**: ETL 流程動畫、雷達圖、設備驗證

### 6.4 技術債清理

| 項目 | 狀態 |
|:---|:---:|
| PRECHECK_CONSTRAINTS SSOT 驅動 | ✅ 已解決 |
| quality_flags 重採樣邏輯 | ✅ 已解決 |
| 測試隔離性 (reset_for_testing) | ✅ 已解決 |
| Parser/Cleaner 介面契約 | ✅ 已確立 |

### 6.5 準備進入 Sprint 3

Sprint 2 已圓滿完成，具備以下條件進入 Sprint 3:

- ✅ 核心 ETL Pipeline (Parser/Cleaner/BatchProcessor) 全數就緒
- ✅ Interface Contract v1.1 嚴格遵循
- ✅ 140 項測試保障品質
- ✅ Demo 展示頁面上線

**Sprint 3 預計方向**: Feature Engineering 模組開發

---

## 七、風險與緩解

| 風險 | 嚴重度 | 狀態 | 緩解措施 |
|:---|:---:|:---:|:---|
| Parser Windows 測試環境限制 | 🟡 Medium | 監控中 | 已在 WSL/Linux 驗證，Windows 環境為 Polars 已知問題 |
| Cleaner 與 Parser 介面不匹配 | 🔴 High | ✅ 已緩解 | Parser 輸出嚴格遵循 Interface Contract #1 |
| BatchProcessor Manifest 格式變更 | 🟡 Medium | ✅ 已緩解 | 與下游 FeatureEngineer 確認格式 |
| PRECHECK_CONSTRAINTS 技術債 | 🔴 High | ✅ 已緩解 | v2.1 已改為 SSOT 驅動分派表 |
| BP L501 `threshold.isoformat()` 錯誤 | 🟡 Medium | ⚠️ 待修復 | 僅影響 E205 錯誤路徑，Sprint 3 前修復 |
| Demo Google Fonts CDN 依賴 | 🟢 Low | 🟢 觀察 | 離線環境視覺降級，不影響功能 |

---

## 八、下一步行動

1. **Sprint 3 規劃啟動**
   - Feature Engineering 模組設計
   - 與 BatchProcessor v1.3 輸出銜接確認

2. **技術文件更新**
   - 更新 Interface Contract 至 v1.2 (納入 BP v1.3 輸出格式)
   - 完善開發者文件

3. **效能基準測試**
   - Parser/Cleaner/BatchProcessor 效能評測
   - 大檔案處理能力測試

---

## 九、參考文件

| 文件 | 路徑 |
|:---|:---|
| 完整任務排程 | [專案任務排程文件.md](./專案任務排程文件.md) |
| Sprint 2 審查報告 | [Sprint_2_Review_Report.md](./Sprint_2_Review_Report.md) |
| Parser PRD | [PRD_Parser_V2.1.md](../parser/_archive/PRD_Parser_V2.1.md) |
| Parser v2.2 PRD | [PRD_Parser_V2.2.md](../parser/PRD_Parser_V2.2.md) |
| Parser v2.2 遷移指南 | [MIGRATION_v2.1_to_v2.2.md](../parser/MIGRATION_v2.1_to_v2.2.md) |
| Cleaner PRD | [PRD_CLEANER_v2.2.md](../cleaner/PRD_CLEANER_v2.2.md) |
| Interface Contract | [PRD_Interface_Contract_v1.1.md](../Interface%20Contract/PRD_Interface_Contract_v1.1.md) |
| Sprint 1 摘要 | [Sprint_1_執行摘要.md](./Sprint_1_執行摘要.md) |

---

**文件結束**

*最後更新: 2026-02-25 | Sprint 2 進度: 4/4 完成（含 Parser v2.2 模組化） | 審查狀態: 全數通過*
