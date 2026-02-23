# Sprint 2 執行摘要

**Sprint 名稱**: 核心 ETL (Core ETL Pipeline)  
**時間範圍**: 第 3-5 週 (2026-02-23 ~ 2026-03-15)  
**狀態**: 🚧 **進行中** (1/3 完成)  
**文件版本**: v1.0  
**建立日期**: 2026-02-23

---

## 一、Sprint 目標

建立資料攝取、清洗、批次處理流程，確保：
- **嚴格契約驗證**: 所有模組輸出符合 Interface Contract v1.0
- **時間基準傳遞**: PipelineContext 時間基準貫穿整個 ETL 流程
- **零間隙對接**: Parser → Cleaner → BatchProcessor 無縫銜接

---

## 二、任務完成狀態

| 任務 | 版本 | 預估工時 | 實際工時 | 狀態 | 測試 |
|:---|:---:|:---:|:---:|:---:|:---:|
| Parser | v2.1 | 4-5天 | 1天 | ✅ **已完成** | 8 案例 |
| Cleaner | v2.2 | 6-7天 | - | 🚧 **準備中** | - |
| BatchProcessor | v1.3 | 5-6天 | - | ⏳ **待開始** | - |
| Sprint 2 Demo | - | 1.5天 | - | ⏳ **待開始** | - |

---

## 三、已完成項目詳情

### ✅ 2.1 Parser v2.1 (2026-02-23 完成)

#### 3.1.1 交付物

| 檔案 | 說明 | 行數 |
|:---|:---|:---:|
| `src/etl/parser.py` | ReportParser v2.1 主實作 | 770+ |
| `src/exceptions.py` | 擴充例外類別 (4 個新類別) | 60+ |
| `config/site_templates.yaml` | 案場配置範本 | 120+ |
| `tests/test_parser_v21.py` | 單元測試 (8 個案例) | 450+ |

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

---

## 四、進行中項目

### 🚧 2.2 Cleaner v2.2 (準備中)

**預計開始**: 2026-02-24  
**相依項目**: Parser v2.1 ✅ (已完成)

**關鍵任務:**
- C-001: Temporal Context 注入 (E000 檢查)
- C-002: FeatureAnnotationManager 整合
- C-005: 語意感知清洗 (device_role)
- C-006: 設備邏輯預檢 (E350)

**風險提醒:**
- ⚠️ 需確保 device_role 不會洩漏到輸出 (E500)
- ⚠️ 設備邏輯預檢需與後續 Optimization 階段一致

---

## 五、待開始項目

### ⏳ 2.3 BatchProcessor v1.3

**關鍵交付物:**
- Parquet 寫入 (INT64/UTC強制)
- Manifest 生成 (v1.3-CA)
- 設備稽核軌跡傳遞

### ⏳ 2.4 Sprint 2 Demo 展示

**展示內容規劃:**
- ETL 三階段流程動畫
- 品質指標雷達圖
- 設備邏輯違規案例

---

## 六、技術決策記錄

### 6.1 Parser 編碼偵測順序

**決策**: UTF-8 → CP950 → UTF-16  
**理由**: 
- 台灣 BAS 系統多數已支援 UTF-8
- Big5 (CP950) 為舊系統相容
- UTF-16 為特殊案例

### 6.2 時區處理策略

**決策**: 無時區資料假設為 Asia/Taipei  
**理由**:
- 台灣案場為主要使用場景
- `site_templates.yaml` 可配置 `assumed_timezone`
- 未來擴展國際案場只需修改配置

### 6.3 標頭搜尋範圍

**決策**: 限制 500 行  
**理由**:
- 平衡效能與準確性
- 絕大多數 BAS 報表標頭在前 100 行內
- 超大檔案不會無限掃描

---

## 七、風險與緩解

| 風險 | 嚴重度 | 狀態 | 緩解措施 |
|:---|:---:|:---:|:---|
| Parser Windows 測試環境限制 | 🟡 Medium | 監控中 | 已在 WSL/Linux 驗證，Windows 環境為 Polars 已知問題 |
| Cleaner 與 Parser 介面不匹配 | 🔴 High | 已緩解 | Parser 輸出嚴格遵循 Interface Contract #1 |
| BatchProcessor Manifest 格式變更 | 🟡 Medium | 監控中 | 與下游 FeatureEngineer 確認格式 |

---

## 八、下一步行動

1. **Cleaner v2.2 開發** (預計 6-7 天)
   - 整合 FeatureAnnotationManager
   - 實作設備邏輯預檢 (E350)
   - 語意感知清洗

2. **整合測試準備**
   - Parser → Cleaner 流程測試
   - 時間基準傳遞驗證

3. **文件更新**
   - Cleaner PRD 審查
   - Interface Contract 更新 (如有需要)

---

## 九、參考文件

| 文件 | 路徑 |
|:---|:---|
| 完整任務排程 | [專案任務排程文件.md](./專案任務排程文件.md) |
| Parser PRD | [PRD_Parser_V2.1.md](../parser/PRD_Parser_V2.1.md) |
| Interface Contract | [PRD_Interface_Contract_v1.1.md](../Interface%20Contract/PRD_Interface_Contract_v1.1.md) |
| Sprint 1 摘要 | [Sprint_1_執行摘要.md](./Sprint_1_執行摘要.md) |

---

**文件結束**

*最後更新: 2026-02-23 | Sprint 2 進度: 1/3 完成 (Parser ✅)*
