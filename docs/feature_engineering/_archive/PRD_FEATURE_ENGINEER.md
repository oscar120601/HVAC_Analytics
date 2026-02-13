# PRD v1.0: 特徵工程實作指南 (Feature Engineering Implementation Guide)

**文件版本:** v1.0
**日期:** 2026-02-12
**負責人:** Oscar Chang
**目標模組:** `src/etl/feature_engineer.py` (New Module)

---

## 1. 執行總綱

本文件是構建全新 **特徵工程模組 (Feature Engineer)** 的施工藍圖。
該模組專注於 **「加法與創造」**，嚴格禁止執行資料清洗或過濾。

**核心職責:**
1. **P1 物理特徵**: 計算濕球溫度 (Wet Bulb)、焓值 (Enthalpy)。
2. **P1 時間特徵**: 提取小時、星期、平假日。
3. **P2 統計特徵**: 滾動平均 (Rolling)、延遲特徵 (Lags)。
4. **P3 互動特徵**: 產生非線性的交互項 (如 `Load^2`)。

---

## Phase 1: 基礎架構與配置

### Step 1.1: 定義特徵配置模型
- **動作**: 編輯 `src/etl/config_models.py`
- **內容**: 新增 `FeatureEngineeringConfig`。
  ```python
  class FeatureConfig(BaseModel):
      enable_physics_features: bool = True  # 是否計算濕球/焓值
      enable_time_features: bool = True     # 是否產生 hour, weekday
      rolling_window_hours: List[int] = [1, 24]  # 滾動視窗大小 (小時)
      lag_hours: List[int] = [1]            # 延遲特徵 (小時)
  ```

### Step 1.2: 建立模組骨架
- **動作**: 建立 `src/etl/feature_engineer.py`
- **內容**:
  - class `FeatureEngineer`:
    - `__init__(self, config: FeatureConfig)`
    - `transform(self, df: pl.DataFrame) -> pl.DataFrame`: 主入口方法。

---

## Phase 2: 物理特徵引擎 (Physics Features)

### Step 2.1: 遷移濕球溫度計算
- **動作**: 從 `cleaner.py` (舊版) 提取 `calculate_wet_bulb_temp` 邏輯，重構至 `src/utils/physics.py` (新工具檔)。
- **要求**:
  - 確保使用 `numpy` 或 `polars` 表達式進行向量化計算 (Vectorized)，**禁止**使用 for loop。
  - 輸入參數統一為 SI 制 (°C, %RH, hPa)。

### Step 2.2: 實作物理轉換層
- **動作**: 在 `FeatureEngineer.transform` 中呼叫物理工具。
- **邏輯**:
  - 識別現有欄位中的 `dry_bulb_temp` 與 `relative_humidity`。
  - 計算 `wet_bulb_temp` 與 `enthalpy`。
  - 將新欄位併入 DataFrame。

---

## Phase 3: 時間與統計特徵 (Time & Stats)

### Step 3.1: 實作週期性時間編碼
- **動作**: 在 `src/etl/feature_engineer.py` 新增 `_generate_time_features`。
- **邏輯**:
  - 解析 `timestamp` 欄位。
  - 產生 `hour`, `day_of_week`, `is_weekend`。
  - (進階) 產生 `hour_sin`, `hour_cos` (將時間映射到圓形空間，避免 23點 與 0點 距離過遠的問題)。

### Step 3.2: 實作 Lag 與 Rolling 特徵
- **動作**: 在 `src/etl/feature_engineer.py` 新增 `_generate_lag_rolling`。
- **注意**: **必須先確保資料的時間序列是連續的** (這在 Cleaner 階段應已由 Resampling 保證)。
- **邏輯**:
  - 對核心變數 (如 `chiller_load`) 執行 `shift(n)` 產生 Lag 特徵。
  - 執行 `rolling_mean(window_size)` 產生趨勢特徵。

---

## Phase 4: 整合與驗證

### Step 4.1: 更新主流程介面
- **動作**: 更新 `src/interface.py`
- **內容**: 在 `clean_data` 之後，`train_model` 之前，插入 `feature_engineer.transform()`。

### Step 4.2: 單元測試
- **動作**: 建立 `tests/test_feature_engineer.py`
- **Case A (Physics)**: 驗證 30°C / 50% RH 的濕球溫度計算結果是否準確。
- **Case B (Time)**: 驗證 23:00 的 `hour_sin/cos` 與 01:00 是否鄰近。
- **Case C (Data Leak)**: 確保 Lag 特徵沒有參照到「未來」的數據。

---

## 5. 交付產物清單

1. `src/etl/feature_engineer.py`: 核心程式碼。
2. `src/utils/physics.py`: 獨立的物理公式庫。
3. `tests/test_feature_engineer.py`: 測試案例。
4. `config/settings.yaml`: 新增 `feature_engineering` 設定區塊。

---

## 6. 下一步指令

**建議順序**：先完成 `DataCleaner (PRD v2.0)` 的實作，確保地基穩固後，再開始本 PRD 的實作。
