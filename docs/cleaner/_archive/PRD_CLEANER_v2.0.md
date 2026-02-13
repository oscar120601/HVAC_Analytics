# PRD v2.0: 資料清洗器實作指南 (DataCleaner Implementation Guide)

**文件版本:** v2.0 (Step-by-Step Implementation Detail)
**日期:** 2026-02-12
**負責人:** Oscar Chang
**目標模組:** [src/etl/cleaner.py](file:///d:/12.任務/HVAC-1/src/etl/cleaner.py)

---

## 1. 執行總綱

本文件是針對 `cleaner.py` 重構的**詳細施工藍圖**。我們將分三個階段進行，每個階段都有明確的「檔案操作指令」。

**核心策略:** 
1. **不破壞現有程式碼**：先建立新模組 (`cleaner_v2.py`)，舊的 (`cleaner.py`) 改名保留。
2. **配置先行**：先定義好 Config 模型，再寫邏輯。
3. **單元感知**：物理計算一律先轉 SI 制（公制）。

---

## Phase 1: 基礎配置與 Pydantic 定義

### Step 1.1: 建立配置模型檔案
- **動作**: 建立新檔案 `src/etl/config_models.py`
- **內容要求**:
  - 定義 `UnitSystem` (Enum): `METRIC`, `IMPERIAL`
  - 定義 `CleaningConfig` (BaseModel):
    - `unit_system`: 預設 `METRIC`
    - `resample_interval`: 預設 `"5m"`
    - `cp_water_poly_coeffs`: 預設 `[4.2, -0.0005]`
    - `max_drop_rate`: 預設 `0.3` (熔斷閾值)
    - `design_capacity_kw`: Optional[float] (額定容量)

### Step 1.2: 更新設定檔
- **動作**: 編輯 `config/settings.yaml`
- **內容要求**: 
  - 新增 `cleaning` 區塊，填入上述參數的預設值。
  - 例如：
    ```yaml
    cleaning:
      unit_system: "imperial"  # 若現有案場是英制
      resample_interval: "5m"
      max_drop_rate: 0.3
    ```

### Step 1.3: 建立配置載入器
- **動作**: 建立/編輯 `src/utils/config_loader.py`
- **內容要求**:
  - 新增函數 `load_cleaning_config(path: str) -> CleaningConfig`。
  - 使用 `yaml.safe_load` 讀取並轉換為 Pydantic 物件。

---

## Phase 2: 核心清洗器重構 (物理引擎)

### Step 2.1: 建立新版 Cleaner 骨架
- **動作**: 建立 `src/etl/cleaner_v2.py`
- **內容要求**:
  - class `DataCleaner`:
    - `__init__(self, config: CleaningConfig)`
    - 保存 config 為成員變數。

### Step 2.2: 實作單位標準化層 (Unit Normalizer)
- **動作**: 在 `cleaner_v2.py` 中新增 helper 方法 `_to_si_units`
- **輸入**: 多個 Series (flow, temp_in, temp_out)
- **邏輯**:
  - 檢查 `self.config.unit_system`。
  - 若為 `IMPERIAL`:
    - Flow: GPM * 3.78541 -> LPM
    - Temp: (°F - 32) * 5/9 -> °C
  - 若為 `METRIC`: 不變。
- **回傳**: 轉換後的三個 Series (LPM, °C, °C)。

### Step 2.3: 實作精確熱平衡驗證
- **動作**: 在 `cleaner_v2.py` 中實作 `validate_heat_balance`
- **邏輯**:
  1. 呼叫 `_to_si_units` 取得公制數據。
  2. 計算 Delta T = `temp_in` - `temp_out`。
  3. 計算平均水溫 `t_avg` = (`temp_in` + `temp_out`) / 2。
  4. 計算 Cp (比熱) = `poly_val(t_avg, self.config.cp_water_poly_coeffs)`。
  5. 計算理論熱負載 `Q_calc (kW)` = `flow (LPM) * delta_T * Cp * density / 60`。
  6. 比較 `Q_calc` 與儀表讀數 `Q_meter` (需注意單位轉換)。
  7. 計算誤差率 `error_pct`。
- **輸出**: 回傳一個 Boolean Series (True = 通過, False = 失敗)。

### Step 2.4: 實作通用重採樣 (Generic Resampler)
- **動作**: 在 `cleaner_v2.py` 中實作 `resample_data`
- **邏輯**:
  - **不要寫死** `endswith("KWH")`。
  - 接受一個 `agg_map` (Dict[str, str]) 參數。
  - 使用 `df.group_by_dynamic(..., every=self.config.resample_interval).agg(...)`。
  - 若 `agg_map` 為空，對數值欄位預設 `mean()`，非數值預設 `first()`。

---

## Phase 3: 安全防護與品質報告

### Step 3.1: 實作熔斷機制 (Circuit Breaker)
- **動作**: 在 `cleaner_v2.py` 的主流程 `clean()` 方法中
- **邏輯**:
  1. 執行所有驗證 (Heat Balance, Affinity, etc.) 得到 `invalid_mask`。
  2. 計算 `drop_count = invalid_mask.sum()`。
  3. 計算 `drop_rate = drop_count / total_rows`。
  4. **檢查**: `if drop_rate > self.config.max_drop_rate`:
     - logger.error("Circuit Breaker Triggered!")
     - 拋出 `CircuitBreakerException` (需在 `src/exceptions.py` 新增)。
     - 或者：回傳原始 DF 並加上標籤 `"DATA_SUSPICIOUS"` (依策略而定)。

### Step 3.2: 產生品質報告
- **動作**: 在 `src/etl/quality_report.py` (新檔案) 或 `cleaner_v2.py`
- **邏輯**:
  - 收集各步驟的統計數據：
    - 原始行數
    - 缺失值填充數
    - 熱平衡失敗數
    - 穩定態佔比
  - 回傳 Dict 或 Pydantic 物件。

---

## Phase 4: 文檔與遷移

### Step 4.1: 更新 README
- **動作**: 更新 `src/etl/README.md` (若無則建立)
- **內容**: 說明如何使用 v2 Cleaner，以及 Config 的設定範例。

### Step 4.2: 建立遷移腳本
- **動作**: 建立 `scripts/migrate_v1_to_v2.py`
- **邏輯**: 讀取舊的 `feature_mapping.py`，輔助生成新的 `settings.yaml` 區塊。

---

## 5. 驗證步驟 (Verification)

每完成一個 Phase，請執行以下檢查：

1.  **Phase 1 完成後**:
    - 執行 `python -c "from src.etl.config_models import CleaningConfig; print(CleaningConfig())"` 
    - 預期結果：印出預設配置，無報錯。

2.  **Phase 2 完成後**:
    - 撰寫單元測試 `tests/test_cleaner_v2.py`。
    - Case A: 輸入 `[100 GPM, 55F, 45F]`，驗證轉換後的 LPM/°C 是否正確。
    - Case B: 輸入完美熱平衡數據，驗證 `validate_heat_balance` 回傳 True。

3.  **Phase 3 完成後**:
    - Case C: 輸入 100 筆全是錯的數據，驗證是否拋出 `CircuitBreakerException`。

---

## 6. 下一步指令

請確認是否準備好開始執行 **Phase 1: 基礎配置**？
