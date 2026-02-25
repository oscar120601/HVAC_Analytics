# PRD v2.1: 報表解析器强健性重構 (ReportParser Robustness Refactoring)

**文件版本:** v2.1 (Interface Contract Alignment & Zero-Gap Integration)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**目標模組:** `src/etl/parser.py` (v2.1+)  
**相依模組:** `src/etl/cleaner.py` (v2.2+), `src/etl/config_models.py` (SSOT)  
**上游規範:** `INTERFACE_CONTRACT_v1.0` (檢查點 #1)  
**預估工時:** 3 ~ 3.5 個工程天（含整合測試）

---

## 1. 執行總綱與變更摘要

### 1.1 版本變更總覽 (v2.0 → v2.1)

| 變更類別 | v2.0 狀態 | v2.1 修正 | 影響層級 |
|:---|:---|:---|:---:|
| **時區輸出** | 輸出 `Asia/Taipei` | **強制輸出 `UTC`** (Breaking Change) | 🔴 Critical |
| **編碼驗證** | 無輸出驗證 | 增加 UTF-8 BOM 殘留檢查 | 🟡 Medium |
| **契約驗證** | 無 | 新增 `_validate_output_contract()` | 🔴 Critical |
| **SSOT 引用** | 無 | 明確引用 `VALID_QUALITY_FLAGS` 進行欄位驗證 | 🟡 Medium |
| **下游銜接** | 隱式契約 | 明確對齊 `Cleaner v2.2` Input Contract | 🔴 Critical |

### 1.2 核心設計原則

1. **契約優先 (Contract-First)**: 所有輸出必須通過 Interface Contract v1.0 檢查點 #1
2. **Single Source of Truth (SSOT)**: 編碼規範、時區規範、欄位命名規範統一引用 `config_models.py`
3. **防禦性輸出**: 寧可拋出例外終止流程，也不輸出不符合契約的資料
4. **零間隙對接**: 確保與 Cleaner v2.2 的記憶體銜接無需額外轉換（時區、編碼、格式）

---

## 2. 下游契約與接口規範 (Cleaner Input Contract)

Parser v2.1 的輸出必須嚴格符合以下規範，這是與 Cleaner v2.2 的**硬性契約**：

### 2.1 欄位與型別規範

| 欄位名稱 | Polars 型別 | 規範限制 | 驗證邏輯 |
|:---|:---|:---|:---|
| `timestamp` | `Datetime(time_unit='ns', time_zone='UTC')` | **強制 UTC**，不可為 None | `dtype.time_zone == "UTC"` |
| `quality_flags` | `List(Utf8)` (可選) | 若存在，值必須 ⊆ `VALID_QUALITY_FLAGS` | 欄位存在性檢查 |
| 數值欄位 | `Float64` | 無單位字元、無科學記號殘留 | 正規表達式驗證 |
| 字串欄位 | `Utf8` | 編碼必須為 UTF-8，無 BOM | `"\ufeff" not in col` |

### 2.2 編碼與字元規範

- **輸出編碼**: 強制 UTF-8 (無 BOM)
- **禁止字元**: 不可包含 `\ufeff` (UTF-8 BOM), `\x00` (Null byte)
- **換行符號**: 統一為 `\n` (LF)，移除 `\r` (CR)

### 2.3 時區強制規範 (關鍵修正)

**無論輸入資料為何種時區，輸出必須為 UTC**：

```python
# 輸入可能性：
# 1. Naive datetime (無時區) → 假設為 Asia/Taipei → 轉換為 UTC
# 2. Asia/Taipei (UTC+8) → 轉換為 UTC  
# 3. 其他時區 (如 America/New_York) → 轉換為 UTC
# 4. 已為 UTC → 直接通過

# 輸出統一為：
# Datetime(time_unit='ns', time_zone='UTC')
```

---

## 3. 分階段實作計畫 (Phase-Based Implementation)

### Phase 1: 基礎建設與 SSOT 引用 (Day 1)

#### Step 1.1: 建立自訂例外類別 (例外分級)

**檔案**: `src/etl/exceptions.py` (若已存在則擴充)

**新增例外類別**:
```python
class ContractViolationError(Exception):
    """違反模組間介面契約 (Interface Contract)"""
    pass

class EncodingError(ContractViolationError):
    """編碼相關錯誤 (無法偵測、BOM殘留、非UTF-8輸出)"""
    pass

class TimezoneError(ContractViolationError):
    """時區轉換錯誤或非預期時區 (E102/E111)"""
    pass

class DataValidationError(Exception):
    """資料內容驗證失敗 (Schema、Nulls、型別)"""
    pass
```

**驗收標準**:
- [ ] 所有例外可被 `parser.py` 正確 import
- [ ] 例外訊息必須包含違反的契約條款編號 (如 `E101_ENCODING_MISMATCH`)

#### Step 1.2: SSOT 配置引用

**檔案**: `src/etl/parser.py` (檔案頂部)

**實作內容**:
```python
from src.etl.config_models import (
    VALID_QUALITY_FLAGS,  # SSOT: 品質標記唯一真相源
    TIMESTAMP_CONFIG,     # SSOT: 時間戳規範
    ParserConfig          # 配置模型
)
```

**驗收標準**:
- [ ] 無硬編碼的 flags 列表 (如 `["FROZEN", "OUTLIER"]`)
- [ ] 時區轉換邏輯引用 `TIMESTAMP_CONFIG["time_zone"]` (應為 "UTC")

---

### Phase 2: 編碼自適應與標頭搜尋 (Day 1-2)

#### Step 2.1: 編碼自動偵測 (含 BOM 處理)

**方法**: `_detect_encoding(file_path: Path) -> str`

**詳細邏輯**:
1. **BOM 優先偵測**:
   ```python
   with open(file_path, 'rb') as f:
       raw = f.read(4)
       if raw.startswith(b'\xef\xbb\xbf'):
           return 'utf-8-sig'  # Python 會自動處理 BOM
       elif raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
           return 'utf-16'
   ```

2. **編碼嘗試順序** (嚴格順序，不可調換):
   - 嘗試 `utf-8`: 使用 `raw.decode('utf-8')`，成功則回傳 `'utf-8'`
   - 嘗試 `cp950` (Big5): 使用 `raw.decode('cp950')`，成功則回傳 `'cp950'`
   - 嘗試 `utf-16`: 使用 `raw.decode('utf-16')`，成功則回傳 `'utf-16'`
   - 全部失敗: 拋出 `EncodingError(f"E101: 無法偵測編碼，已嘗試 UTF-8/Big5/UTF-16")`

**驗收標準**:
- [ ] UTF-8 BOM 檔案 (`\ufeff`) 不會在欄位名稱或資料中殘留
- [ ] Big5 編碼檔案 (如台灣 BAS 系統匯出) 正確讀取
- [ ] 編碼錯誤檔案拋出 `E101_ENCODING_MISMATCH`

#### Step 2.2: 智慧標頭搜尋 (多語系與一致性驗證)

**方法**: `_find_header_line(file_path: Path, encoding: str) -> int`

**詳細邏輯**:

1. **關鍵字定義** (引用 SSOT):
   ```python
   HEADER_KEYWORDS = {
       'timestamp': ['Date', 'Time', '日期', '時間', 'DateTime', 'Timestamp', '时间'],
       'required': ['Date', '日期']  # 必須至少存在一個
   }
   ```

2. **搜尋範圍**: 前 500 行 (可配置 `max_header_scan_lines`)

3. **候選行評分**:
   - 找到同時包含 `Date/日期` 與 `Time/時間` 的行 → 分數 +2
   - 找到包含 `DateTime/Timestamp` 的行 → 分數 +2
   - 該行欄位數量 > 3 → 分數 +1

4. **分隔符一致性驗證** (防誤觸):
   ```python
   candidate_line = lines[header_line]
   next_line = lines[header_line + 1]
   
   # 計算分隔符數量 (逗號、Tab、分號)
   candidate_delims = count_delimiters(candidate_line)
   next_delims = count_delimiters(next_line)
   
   # 必須一致 (容差 ±1，考慮最後一欄可能為空)
   if abs(candidate_delims - next_delims) > 1:
       continue  # 跳過此候選行，繼續搜尋
   ```

5. **失敗處理**:
   - 若找不到標頭行，拋出 `ContractViolationError("E104: 無法定位標頭行，已掃描 500 行")`
   - 禁止 fallback 到硬編碼行號 (如 211)

**驗收標準**:
- [ ] 中文標頭 (`日期`, `時間`) 正確識別
- [ ] 包含特殊前綴的標頭 (`<>Date`, `"Time"`) 正規化後識別
- [ ] 中繼資料行 (分隔符數量與資料行不符) 不會被誤判為標頭
- [ ] 無標頭檔案拋出明確例外 (非靜默 fallback)

#### Step 2.3: 標頭正規化

**方法**: `_normalize_header(headers: List[str]) -> List[str]`

**處理規則**:
1. 移除前後空白: `strip()`
2. 移除引號: `replace('"', '').replace("'", '')`
3. 移除特殊前綴: `replace('<>', '')`
4. 統一命名: 將 `日期` 映射為 `Date`，`時間` 映射為 `Time` (為後續 timestamp 合併做準備)
5. 驗證唯一性: 若正規化後仍有重複欄位名稱，拋出 `DataValidationError`

**驗收標準**:
- [ ] `"<>Date"` → `Date`
- [ ] `"  Time  "` → `Time`
- [ ] `"溫度_1"` → `溫度_1` (保留中文，但確保無空白)

---

### Phase 3: 資料解析與清洗 (Day 2)

#### Step 3.1: 髒資料處理與強制轉型

**方法**: `_clean_and_cast(df: pl.DataFrame) -> pl.DataFrame`

**詳細邏輯**:

1. **Null 值定義** (擴充):
   ```python
   NULL_VALUES = [
       "", "NA", "null", "NULL", 
       "---", "Error", "N/A", "OFF", "OFFLINE", 
       "#VALUE!", "#N/A", "None", "--"
   ]
   ```

2. **數值欄位清洗** (針對 BAS 常見髒資料):
   ```python
   for col in numeric_columns:
       # 步驟 1: 移除單位與非數字字元 (保留數字、小數點、負號、科學記號)
       df = df.with_columns(
           pl.col(col).str.replace_all(r"[^0-9.\-eE]", "").alias(col)
       )
       
       # 步驟 2: 空字串轉為 Null
       df = df.with_columns(
           pl.when(pl.col(col) == "").then(None).otherwise(pl.col(col)).alias(col)
       )
       
       # 步驟 3: 強制轉型 Float64 (無法轉型則設為 Null，非拋出例外)
       df = df.with_columns(
           pl.col(col).cast(pl.Float64, strict=False)
       )
   ```

3. **時間欄位合併**:
   - 若存在分開的 `Date` 與 `Time` 欄位，合併為 `timestamp`
   - 格式: `yyyy-MM-dd HH:mm:ss` (假設為 Asia/Taipei 輸入，後續轉 UTC)

**驗收標準**:
- [ ] `"25.3 C"` → `25.3` (Float64)
- [ ] `"100%"` → `100.0` (Float64)
- [ ] `"---"` → `null`
- [ ] `"Error"` → `null`
- [ ] 轉型失敗不拋出例外，設為 Null 並記錄 Warning

---

### Phase 4: 時區標準化 (關鍵修正) (Day 2-3)

#### Step 3.4: 時區強制轉換 (v2.1 核心修正)

**方法**: `_standardize_timezone(df: pl.DataFrame) -> pl.DataFrame`

**詳細邏輯**:

```python
def _standardize_timezone(self, df: pl.DataFrame) -> pl.DataFrame:
    """
    強制將時間戳轉換為 UTC (Interface Contract v1.0 強制規範)
    
    處理流程:
    1. 檢查輸入時區
    2. 若無時區 (Naive)，假設為 Asia/Taipei (台灣 BAS 系統慣例)
    3. 轉換為 UTC
    4. 驗證輸出時區
    """
    if "timestamp" not in df.columns:
        raise ContractViolationError("E103: 缺少必要欄位 'timestamp'")
    
    ts_col = df["timestamp"]
    
    # 情況 1: 已為 UTC → 直接通過 (但需確保 time_unit='ns')
    if str(ts_col.dtype.time_zone) == "UTC":
        self.logger.debug("輸入已為 UTC，僅確認 time_unit")
        return df.with_columns(
            pl.col("timestamp").dt.cast_time_unit("ns")
        )
    
    # 情況 2: 為其他時區 (如 Asia/Taipei) → 轉換為 UTC
    if ts_col.dtype.time_zone is not None:
        self.logger.info(f"將時區 {ts_col.dtype.time_zone} 轉換為 UTC")
        return df.with_columns(
            pl.col("timestamp")
            .dt.convert_time_zone("UTC")
            .dt.cast_time_unit("ns")  # 確保 nanoseconds
        )
    
    # 情況 3: 無時區 (Naive) → 假設為 Asia/Taipei 後轉 UTC
    # 【注意】這是針對台灣 BAS 系統的業務邏輯，若擴展至其他地區需改為配置
    self.logger.warning("時間戳無時區資訊，假設為 Asia/Taipei 並轉換為 UTC")
    return df.with_columns(
        pl.col("timestamp")
        .dt.replace_time_zone("Asia/Taipei")  # 先賦予時區
        .dt.convert_time_zone("UTC")           # 再轉換
        .dt.cast_time_unit("ns")
    )
```

**關鍵驗證點**:
- [ ] 輸出 `df.schema["timestamp"]` 必須顯示 `Datetime(time_unit='ns', time_zone='UTC')`
- [ ] 輸入 `Asia/Taipei` (如 `2026-02-13 08:00:00+08:00`) → 輸出 `2026-02-13 00:00:00+00:00`
- [ ] 輸入無時區 (如 `2026-02-13 08:00:00`) → 視為 `Asia/Taipei` → 輸出 `2026-02-13 00:00:00+00:00`

---

### Phase 5: 輸出契約驗證 (Day 3)

#### Step 3.5: 輸出契約驗證 (Output Contract Validation)

**方法**: `_validate_output_contract(df: pl.DataFrame) -> None`

**詳細邏輯**:

```python
def _validate_output_contract(self, df: pl.DataFrame) -> None:
    """
    最終輸出驗證 (Interface Contract v1.0 檢查點 #1)
    
    驗證項目:
    1. 必要欄位存在性
    2. 時間戳時區與精度
    3. 編碼正確性 (無 BOM)
    4. Quality flags 合法性 (若存在)
    """
    errors = []
    
    # 1. 必要欄位檢查 (E103)
    required_cols = ["timestamp"]
    missing = set(required_cols) - set(df.columns)
    if missing:
        errors.append(f"E103: 缺少必要欄位: {missing}")
    
    # 2. 時間戳型別與時區檢查 (E102)
    ts_dtype = df["timestamp"].dtype
    if not isinstance(ts_dtype, pl.Datetime):
        errors.append(f"E102: timestamp 必須為 Datetime，得到 {ts_dtype}")
    elif str(ts_dtype.time_zone) != "UTC":
        errors.append(f"E102: timestamp 時區必須為 UTC，得到 {ts_dtype.time_zone}")
    elif ts_dtype.time_unit != "ns":
        errors.append(f"E102: timestamp 精度必須為 nanoseconds，得到 {ts_dtype.time_unit}")
    
    # 3. 編碼檢查 (E101) - 確保無 BOM 殘留
    for col in df.columns:
        if df[col].dtype == pl.Utf8:
            if df[col].str.contains("\ufeff").any():
                errors.append(f"E101: 欄位 '{col}' 包含 UTF-8 BOM 殘留")
            if df[col].str.contains("\x00").any():
                errors.append(f"E101: 欄位 '{col}' 包含 Null byte")
    
    # 4. Quality Flags 合法性檢查 (E103)
    if "quality_flags" in df.columns:
        actual_flags = set()
        for flags in df["quality_flags"]:
            if flags:
                actual_flags.update(flags)
        
        # 注意: Parser 通常不產生 quality_flags，但若產生必須符合 SSOT
        invalid_flags = actual_flags - set(VALID_QUALITY_FLAGS)
        if invalid_flags:
            errors.append(
                f"E103: quality_flags 包含未定義的標記: {invalid_flags}. "
                f"SSOT 允許: {VALID_QUALITY_FLAGS}"
            )
    
    # 5. 數值欄位型別檢查
    for col in df.columns:
        if col in ["timestamp", "quality_flags"]:
            continue
        # 所有非時間/標記欄位應為 Float64 (或 Int64，但統一為 Float64 更安全)
        if df[col].dtype not in [pl.Float64, pl.Int64]:
            errors.append(f"E103: 欄位 '{col}' 型別為 {df[col].dtype}，預期為數值型別")
    
    if errors:
        raise ContractViolationError(
            f"Parser 輸出契約驗證失敗 ({len(errors)} 項):\n" + "\n".join(errors)
        )
```

**驗收標準**:
- [ ] 時區非 UTC 時拋出 `ContractViolationError` (E102)
- [ ] 欄位含 BOM 時拋出 `ContractViolationError` (E101)
- [ ] 缺少 `timestamp` 時拋出 `ContractViolationError` (E103)

---

### Phase 6: 案場配置與擴展 (Day 3)

#### Step 4.1: 案場設定檔結構 (Site Templates)

**檔案**: `config/site_templates.yaml`

**結構**:
```yaml
schema_version: "2.1"

default:
  encoding: auto          # auto | utf-8 | cp950 | utf-16
  delimiter: ","          # 自動偵測時的優先順序: , → \t → ;
  header_keywords:
    date: ["Date", "日期", "date", "DATE"]
    time: ["Time", "時間", "time", "TIME"]
    datetime: ["DateTime", "Timestamp", "日期時間"]
  
  # 時區設定 (v2.1 新增，用於 naive datetime 的預設賦值)
  assumed_timezone: "Asia/Taipei"  # 僅在輸入無時區時使用
  
  null_values: ["", "NA", "null", "---", "Error", "N/A", "OFF", "OFFLINE", "#VALUE!"]
  
  # 欄位名稱映射 (標準化對照表)
  column_mapping:
    "冰水主機電流": "chiller_current"
    "冷卻水塔溫度": "ct_temp"
    "外氣溫度": "oat"

# 長庚醫院桃園院區
cgmh_ty:
  inherit: default
  header_prefix: "<>"           # 特殊前綴處理
  assumed_timezone: "Asia/Taipei"
  
# 遠雄 O3
farglory_o3:
  inherit: default
  delimiter: "\t"               # Tab 分隔
  encoding: cp950               # 固定編碼 (效能優化)
```

#### Step 4.2: 配置載入與繼承解析

**方法**: `__init__(self, site_id: str = "default")`

**詳細邏輯**:
```python
def __init__(self, site_id: str = "default"):
    self.site_id = site_id
    self.config = self._load_site_config(site_id)
    self.logger = get_logger(f"parser.{site_id}")

def _load_site_config(self, site_id: str) -> Dict:
    """載入配置並處理繼承 (inherit)"""
    with open("config/site_templates.yaml", 'r', encoding='utf-8') as f:
        all_configs = yaml.safe_load(f)
    
    if site_id not in all_configs:
        raise ConfigurationError(f"未定義的案場 ID: {site_id}")
    
    config = all_configs[site_id]
    
    # 處理繼承
    if "inherit" in config:
        parent_id = config.pop("inherit")
        parent_config = all_configs.get(parent_id, {})
        # 深度合併 (子配置覆蓋父配置)
        merged = {**parent_config, **config}
        return merged
    
    return config
```

---

## 4. 完整方法呼叫鏈 (Call Chain)

```
parse_file(file_path)
  ├── _detect_encoding(file_path) → encoding
  ├── _find_header_line(file_path, encoding) → header_line
  ├── pl.read_csv(
  │     encoding=encoding,
  │     skip_rows=header_line,
  │     null_values=config["null_values"]
  │   ) → raw_df
  ├── _normalize_header(raw_df.columns) → normalized_df
  ├── _clean_and_cast(normalized_df) → cleaned_df
  ├── _standardize_timezone(cleaned_df) → utc_df (關鍵)
  ├── _validate_output_contract(utc_df) → void (關鍵)
  └── return utc_df
```

---

## 5. 錯誤代碼對照表 (Error Codes)

| 錯誤代碼 | 名稱 | 發生階段 | 使用者訊息 (User Message) | 處理建議 |
|:---|:---|:---:|:---|:---|
| **E101** | `ENCODING_MISMATCH` | Step 2.1 | 無法偵測檔案編碼，或輸出包含非法字元 (BOM) | 確認檔案為 UTF-8/Big5/UTF-16 之一；檢查是否含 BOM |
| **E102** | `TIMEZONE_VIOLATION` | Step 3.5 | 輸出時間戳時區非 UTC，或精度非 nanoseconds | 檢查 `_standardize_timezone` 邏輯 |
| **E103** | `CONTRACT_VIOLATION` | Step 3.5 | 缺少必要欄位 (timestamp)，或 quality_flags 未定義 | 確認標頭行正確識別；更新 SSOT flags 定義 |
| **E104** | `HEADER_NOT_FOUND` | Step 2.2 | 掃描 500 行仍無法定位標頭 | 手動檢查檔案格式；更新 header_keywords |
| **E105** | `COLUMN_VALIDATION` | Step 3.1 | 欄位正規化後重複，或數值轉型失敗率過高 (>50%) | 檢查髒資料處理邏輯；確認 column_mapping |

---

## 6. 測試與驗證計畫 (Test Plan)

### 6.1 單元測試 (Unit Tests)

**檔案**: `tests/test_parser_v21.py`

| 測試案例 ID | 描述 | 輸入 | 預期輸出 | 對應 Step |
|:---|:---|:---|:---|:---:|
| P21-001 | UTF-8 BOM 處理 | UTF-8 with BOM CSV | 無 BOM 殘留，欄位名稱正確 | 2.1 |
| P21-002 | Big5 編碼偵測 | Big5 編碼 CSV (台灣 BAS) | 正確解析中文標頭 | 2.1 |
| P21-003 | 時區轉換 Asia/Taipei → UTC | `2026-02-13 08:00:00+08:00` | `2026-02-13 00:00:00+00:00` | 3.4 |
| P21-004 | Naive datetime 假設時區 | `2026-02-13 08:00:00` (無時區) | 視為 Asia/Taipei → UTC | 3.4 |
| P21-005 | 時區錯誤攔截 | 輸出強制檢查攔截非 UTC | 拋出 `E102_TIMEZONE_VIOLATION` | 3.5 |
| P21-006 | 髒資料清洗 | `"25.3 C"`, `"---"`, `"Error"` | `25.3`, `null`, `null` | 3.1 |
| P21-007 | 標頭分隔符一致性 | 中繼資料行含 "Date" 但分隔符不同 | 正確跳過，找到真實標頭 | 2.2 |
| P21-008 | 輸出契約驗證 | 缺少 timestamp 欄位 | 拋出 `E103_CONTRACT_VIOLATION` | 3.5 |

### 6.2 整合測試 (Integration Tests)

**檔案**: `tests/test_parser_cleaner_integration.py`

| 測試案例 ID | 描述 | 驗證目標 |
|:---|:---|:---|
| INT-001 | Parser v2.1 → Cleaner v2.2 | Cleaner 無需時區轉換即可處理 |
| INT-002 | Parser v2.1 → BatchProcessor v1.3 | Parquet 寫入驗證通過 (INT64/UTC) |
| INT-003 | SSOT Flags 一致性 | Parser 不產生非法 flags |

---

## 7. 風險評估與緩解 (Risk Assessment)

| 風險 | 嚴重度 | 可能性 | 緩解措施 |
|:---|:---:|:---:|:---|
| **時區轉換效能** (大檔案時區轉換耗時) | 🟡 Medium | High | 使用 Polars 原生 `convert_time_zone` (Rust 後端，已優化)；若仍過慢，可考慮在 Cleaner 層做批次轉換 |
| **Naive 時區假設錯誤** (非台灣案場使用) | 🔴 High | Medium | 在 `site_templates.yaml` 明確定義 `assumed_timezone`，預設為 `Asia/Taipei` 但可配置；非台灣案場必須明確設定 |
| **編碼偵測誤判** (UTF-8 相容的 Big5 字元) | 🟡 Medium | Low | 優先偵測 BOM；提供 `encoding=auto` 覆蓋選項；記錄偵測結果供除錯 |
| **記憶體占用** (大檔案一次性讀取) | 🟡 Medium | High | 目前設計為 In-Memory；若檔案 > 1GB，建議在 CLI 層先切割檔案 (未來 v2.2 可考慮 Streaming) |
| **向下相容性** (舊版 Cleaner 無法處理 UTC) | 🟡 Medium | Medium | 版本檢查：Parser v2.1 必須搭配 Cleaner v2.2+；若偵測到舊版 Cleaner，拋出相容性警告 |

---

## 8. 版本相容性矩陣 (Version Compatibility)

| Parser | Cleaner | BatchProcessor | 相容性 | 說明 |
|:---:|:---:|:---:|:---:|:---|
| v2.1 | v2.2+ | v1.3+ | ✅ 完全相容 | 推薦配置，零間隙對接 |
| v2.1 | v2.1 | v1.2 | ⚠️ 部分相容 | Cleaner 需啟動時區容錯 (自動轉換 UTC)，效能略降 |
| v2.1 | v2.0 | 任意 | ❌ 不相容 | Cleaner v2.0 期望 Asia/Taipei，會發生時區錯誤 |
| v2.0 | 任意 | 任意 | ⚠️ 已棄用 | v2.0 輸出 Asia/Taipei，不建議繼續使用 |

---

## 9. 交付物清單 (Deliverables)

### 9.1 程式碼檔案
1. `src/etl/parser.py` - 主要實作 (含 v2.1 所有修正)
2. `src/etl/exceptions.py` - 例外類別定義 (若尚未存在)
3. `config/site_templates.yaml` - 案場配置範本 (含 v2.1 時區設定)

### 9.2 測試檔案
4. `tests/test_parser_v21.py` - v2.1 專屬單元測試
5. `tests/test_parser_cleaner_integration.py` - 整合測試

### 9.3 文件檔案
6. `docs/parser/PRD_PARSER_v2.1.md` - 本文件
7. `docs/parser/CHANGELOG_v2.0_to_v2.1.md` - 升級指引 (供維運團隊)

---

## 10. 附錄：與 Interface Contract v1.0 對照

| Interface Contract #1 檢查項 | Parser v2.1 實現位置 | 驗證方式 |
|:---|:---|:---|
| timestamp 時區必須為 UTC | Step 3.4 (`_standardize_timezone`) | Step 3.5 (`_validate_output_contract`) |
| 編碼必須為 UTF-8 | Step 2.1 (編碼偵測與轉換) | Step 3.5 (BOM 殘留檢查) |
| 必要欄位必須包含 timestamp | Step 3.4 (存在性檢查) | Step 3.5 (欄位檢查) |
| 無未來資料 (選配) | Step 3.4 (可選檢查) | - |

---

## 11. 驗收簽核 (Sign-off Checklist)

- [ ] **編碼處理**: Big5/UTF-8/UTF-16 自動偵測，無 BOM 殘留
- [ ] **時區強制**: 輸出絕對為 UTC (ns 精度)，通過 `E002` 驗證
- [ ] **契約驗證**: `_validate_output_contract` 完整實作，錯誤代碼正確
- [ ] **標頭搜尋**: 中文標頭支援，無硬編碼 fallback
- [ ] **髒資料**: `---`, `25.3 C` 等 BAS 常見髒資料正確處理
- [ ] **整合測試**: 與 Cleaner v2.2 無縫銜接 (無需時區轉換)
- [ ] **SSOT 引用**: 無硬編碼 flags，引用 `config_models.VALID_QUALITY_FLAGS`
- [ ] **向下相容**: 明確標記與舊版 Cleaner 不相容，避免誤用

---
