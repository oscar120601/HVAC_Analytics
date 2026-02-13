# PRD v2.1: 資料清洗器實作指南 (DataCleaner Implementation Guide)

**文件版本:** v2.1 (Interface Contract Alignment)
**日期:** 2026-02-12
**負責人:** Oscar Chang
**目標模組:** `src/etl/cleaner.py` (v2.0+)
**下游模組:** `src/etl/feature_engineer.py` (v1.2+)

---

## 1. 執行總綱與變更重點

本文件是針對 `cleaner.py` 重構的**詳細施工藍圖**。 V2.1 版的核心變更在於 **「介面契約 (Interface Contract)」** 的嚴格化。

**核心目標:** 
1. **Gatekeeper (守門員)**：確保髒數據絕不進入下游。
2. **Contract Provider (契約提供者)**：保證輸出格式完全符合 `Feature Engineer v1.2` 的輸入要求。

---

## 2. 輸出介面契約 (Output Contract)

這是有史以來最嚴格的規範，**Cleaner 必須保證**輸出 DataFrame 符合以下規格，否則視為清洗失敗。

### 2.1 必備欄位與格式
| 欄位名稱 | 類型 (Polars) | 內容規範 | 對應 Feature Engineer 需求 |
|:---|:---|:---|:---|
| `timestamp` | `Datetime(time_unit='us', time_zone='UTC')` | 必須是 UTC，且無重複、無亂序 | `InputContract.timestamp_tz="UTC"` |
| `quality_flags` | `List(Utf8)` | 空列表 `[]` 代表乾淨，否則包含錯誤代碼 | `InputContract.quality_flags_handling` |
| `*_temp` | `Float64` | 單位必須是 **攝氏 (°C)** | Feature Engineer 物理公式輸入 |
| `*_flow` | `Float64` | 單位必須是 **LPM** (或 GPM，需統一) | - |
| `*_kw` | `Float64` | 單位必須是 **kW** | - |

### 2.2 資料完整性保證
1.  **無未來數據**：`timestamp` 不得超過 `Now()`。
2.  **時序連續性**：若設定 `resample_interval="15m"`，則輸出必須嚴格遵循 15 分鐘間隔（允許缺失值以 Null 表示，但時間軸不能斷）。
3.  **元數據 (Metadata)**：每個欄位必須能透過 `feature_mapping` 查詢到 `physical_type`（供 Feature Engineer 的 Group Policy 使用）。

---

## Phase 1: 基礎配置與 Pydantic 定義

### Step 1.1: 建立配置模型檔案
- **動作**: 建立新檔案 `src/etl/config_models.py`
- **內容要求**:
  - 定義 `UnitSystem` (Enum): `METRIC`, `IMPERIAL`
  - 定義 `OutputSchema` (Pydantic 模型，新增於 v2.1):
    ```python
    class OutputSchema(BaseModel):
        ensure_utc: bool = True
        ensure_regular_interval: bool = True
        add_quality_flags: bool = True
    ```
  - 定義 `CleaningConfig` (BaseModel):
    - `unit_system`: 預設 `METRIC`
    - `output_contract`: OutputSchema (預設開啟所有檢查)
    - ... (其餘同 v2.0)

### Step 1.2: 更新設定檔
- **動作**: 編輯 `config/settings.yaml`
- **內容要求**: 
  - 新增 `cleaning` 區塊，填入上述參數的預設值。

---

## Phase 2: 核心清洗器重構 (物理引擎)

### Step 2.1: 建立新版 Cleaner 骨架
- **動作**: 建立 `src/etl/cleaner_v2.py`
- **內容要求**:
  - class `DataCleaner`:
    - `__init__(self, config: CleaningConfig)`
    - `clean(self, df: pl.DataFrame) -> pl.DataFrame`: 主入口，必須回傳符合契約的 DF。

### Step 2.2: 實作單位標準化層 (Unit Normalizer)
- **動作**: 在 `cleaner_v2.py` 中新增 helper 方法 `_to_si_units`
- **邏輯**: (同 v2.0，但強調輸出必須是 float64)

### Step 2.3: 實作精確熱平衡驗證 (產生 Flags)
- **動作**: 在 `cleaner_v2.py` 中實作 `validate_heat_balance`
- **邏輯**:
  - 計算熱平衡誤差。
  - **關鍵變更**: 若誤差過大，不刪除數據，而是將 `"HEAT_IMBALANCE"` 字串 append 到 `quality_flags` 欄位中。
  - 若 `quality_flags` 欄位不存在，則先初始化為空列表。

### Step 2.4: 實作通用重採樣 (Resampler)
- **動作**: 在 `cleaner_v2.py` 中實作 `resample_data`
- **邏輯**:
  - 使用 `upsample` 或 `group_by_dynamic` 確保時間軸連續。
  - **關鍵變更**: 在重採樣後，必須檢查 `timestamp` 是否均勻，若有斷點需補上 Null 列（Feature Engineer 需要連續時間軸來做 Shift/Rolling）。

---

## Phase 3: 安全防護與契約驗證

### Step 3.1: 實作熔斷機制 (Circuit Breaker)
- **動作**: 同 v2.0，若品質太差則報警。

### Step 3.2: 輸出契約驗證 (Output Validator)
- **動作**: 在 `clean() ` 方法的最後，呼叫 `_validate_output_contract(df)`。
- **邏輯**:
  1. 檢查 `timestamp` 是否為 UTC。
  2. 檢查 `quality_flags` 欄位是否存在。
  3. 檢查時間軸是否連續 (若 config 要求)。
  4. 若驗證失敗，拋出 `ContractViolationError` (這是嚴重的開發錯誤，非數據錯誤)。

---

## Phase 4: 文檔與遷移

### Step 4.1: 更新 README
- **動作**: 更新 `src/etl/README.md`，強調 Output Contract。

### Step 4.2: 建立遷移腳本
- **動作**: 同 v2.0。

---

## 5. 驗證步驟 (Verification)

每完成一個 Phase，請執行以下檢查：

1.  **Phase 1 完成後**:
    - 驗證 Config 載入無誤。

2.  **Phase 2 完成後**:
    - 單元測試：輸入不平衡數據，驗證 `quality_flags` 包含 `"HEAT_IMBALANCE"`。
    - 單元測試：輸入缺漏時間點，驗證 Resampler 補齊了 Null 列。

3.  **Phase 3 完成後**:
    - **整合測試 (關鍵)**：將 Cleaner 的輸出丟給 Feature Engineer v1.2 的 `_validate_input`，必須 **PASS**。

---

## 6. 下一步指令

請確認是否準備好開始執行 **Phase 1: 基礎配置**？
