# PRD v1.1: 特徵工程強健性實作指南 (Feature Engineering Implementation Guide)

**文件版本:** v1.1  
**日期:** 2026-02-12  
**負責人:** Oscar Chang  
**目標模組:** `src/etl/feature_engineer.py` (New Module)  
**相依模組:** `src/etl/cleaner.py` (v2.0+), `src/utils/physics.py`  
**預估工時:** 3 ~ 4 個工程天（含整合測試）

---

## 1. 執行總綱與設計原則

### 1.1 核心職責
本模組專注於 **「加法與創造」**，嚴格禁止執行資料清洗或過濾。所有輸入資料必須先經過 `DataCleaner` 處理。

**設計原則：**
1. **防禦式設計**：即使 Cleaner 輸出異常（含 Null、空缺），仍不拋出致命錯誤
2. **冪等性 (Idempotency)**：相同輸入執行多次，輸出必須完全一致
3. **記憶體安全**：禁止產生維度爆炸特徵，強制限制 Rolling Window 大小

### 1.2 輸入輸出契約（Input/Output Contract）

```python
class FeatureEngineerInputContract:
    """
    Feature Engineer 對輸入資料的嚴格要求
    由 DataCleaner 保證，或由本模組在 transform() 開頭驗證
    """
    required_columns: List[str] = ["timestamp"]  # 必須包含時間戳欄位
    expected_frequency: str = "15min"            # 資料頻率，用於驗證時間連續性
    timestamp_tz: str = "UTC"                    # 強制 UTC，禁止時區轉換
    
    # 與 Cleaner 的銜接策略
    quality_flags_handling: Literal["drop", "onehot", "ignore"] = "onehot"
    # drop: 刪除有標記的列（保守，損失資料）
    # onehot: 將標記拆解為特徵（推薦，保留資訊）
    # ignore: 忽略標記（快速，但可能引入雜訊）

class FeatureEngineerOutputContract:
    """
    輸出資料規格保證
    """
    feature_naming_convention: str = "{original_col}_{transformation}_{parameters}"
    # 例：chiller_load_rollmean_96 (15分鐘資料，96點=24小時)
    null_strategy: str = "propagate_with_flag"   # Null 傳播但標記，不隱藏
```

### 1.3 功能範圍 (In-Scope vs Out-of-Scope)

| 範圍 | 包含項目 (In-Scope) | 排除項目 (Out-of-Scope) |
|:---|:---|:---|
| **P1 物理特徵** | 濕球溫度 (Wet Bulb)、焓值 (Enthalpy)<br>（從 Cleaner 遷移至此） | 單位轉換（由 Cleaner 處理後輸入 SI 制） |
| **P1 時間特徵** | 小時、星期、平假日<br>週期性編碼 (sin/cos) | 節假日判斷（需外部日曆 API，超出範圍） |
| **P2 統計特徵** | Lag 特徵 (延遲)<br>Rolling 統計（平均、標準差、最大/最小） | 複雜統計（如指數加權移動平均 EWM，P3 考慮） |
| **P3 互動特徵** | **Out-of-Scope for v1.1**<br>（保留配置介面但標記為未實作） | 非線性交互項（如 `Load^2`、`Load × Temp`） |

---

## 2. 系統架構與配置

### 2.1 與 Cleaner PRD 的整合配置

統一配置檔結構（與 Cleaner PRD 共用 `etl_pipeline` 區塊）：

```yaml
# config/settings.yaml
etl_pipeline:
  cleaner:
    schema_version: "2.0"
    # ... Cleaner 設定（見 Cleaner PRD）
  
  feature_engineer:
    schema_version: "1.1"
    
    # 輸入契約驗證
    input_contract:
      quality_flags_handling: "onehot"  # drop | onehot | ignore
      null_handling: "propagate"        # propagate | fail_fast
      
    # 物理特徵
    physics_features:
      enabled: true
      library: "psychrolib"             # 或自研 ASHRAE 公式
      input_validation:
        temp_range: [-40, 60]           # °C，超出範圍回傳 Null
        rh_range: [0, 100]              # %，超出範圍回傳 Null
        pressure_default: 1013.25       # hPa，若輸入缺漏使用預設值
      
    # 時間特徵
    time_features:
      enabled: true
      cyclical_encoding: true           # 產生 sin/cos
      components: ["hour", "day_of_week", "month", "is_weekend"]
      
    # 統計特徵（關鍵：防維度爆炸）
    stats_features:
      enabled: true
      lag_intervals: [1, 4]             # 1個區間, 4個區間（非絕對時間）
      rolling_windows: [4, 96]          # 4區間(1h), 96區間(24h) - 以資料點計
      max_rolling_window_points: 1000   # 【安全限制】禁止超過 1000 點的視窗
      aggregations: ["mean", "std", "min", "max"]
      
    # 輸出控制
    output:
      drop_original_flags: false        # 是否刪除輸入的 quality_flags 欄位
      add_feature_metadata: true        # 是否加入 feature_source 中繼欄位
```

### 2.2 Feature Mapping 整合

`feature_mapping.py` 需擴充以支援特徵工程：

```python
class FeatureMeta(BaseModel):
    # 繼承自 Cleaner PRD 的 ColumnMeta
    is_target: bool = False            # 是否為目標變數（不應產生 Lag）
    enable_lag: bool = True            # 是否允許產生 Lag 特徵
    enable_rolling: bool = True        # 是否允許產生 Rolling 特徵
    
def get_features_for_engineering(site_config: dict) -> List[FeatureMeta]:
    """回傳允許進行特徵工程的欄位列表（排除 ID、狀態碼等）"""
    ...
```

---

## 3. 分階段實作計畫

### Phase 1: 基礎架構與安全機制 (預估 1 天)

#### Step 1.1: 建立配置模型與輸入驗證
**檔案**: `src/etl/config_models.py`（擴充）

```python
from pydantic import BaseModel, validator

class StatsConfig(BaseModel):
    lag_intervals: List[int]
    rolling_windows: List[int]
    max_rolling_window_points: int = 1000
    
    @validator('rolling_windows')
    def check_window_size(cls, v):
        if any(x > 1000 for x in v):
            raise ValueError(f"Rolling window exceeds safety limit of 1000 points")
        return v

class FeatureEngineeringConfig(BaseModel):
    schema_version: Literal["1.1"] = "1.1"
    input_contract: FeatureEngineerInputContract
    physics_features: PhysicsConfig
    time_features: TimeConfig
    stats_features: StatsConfig
```

#### Step 1.2: 建立模組骨架與防禦機制
**檔案**: `src/etl/feature_engineer.py`

```python
class FeatureEngineer:
    def __init__(self, config: FeatureEngineeringConfig):
        self.config = config
        self._validation_passed = False
        
    def _validate_input(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        輸入驗證與預處理：
        1. 檢查 required_columns 存在
        2. 驗證時間戳連續性（無跳躍或重複）
        3. 處理 quality_flags（依策略 drop/onehot/ignore）
        4. 記憶體預檢（估算產生特徵後的記憶體使用）
        """
        # 時間連續性檢查（防止 Temporal Leakage）
        if self.config.input_contract.expected_frequency:
            # 驗證間隔是否恆定
            pass
            
    def transform(self, df: pl.DataFrame, cutoff_timestamp: Optional[datetime] = None) -> pl.DataFrame:
        """
        主入口方法
        
        Args:
            cutoff_timestamp: 【防資料洩漏】確保所有特徵計算不使用此時間點之後的資料
                              用於訓練/推論分離場景
        """
        # 1. 輸入驗證
        df = self._validate_input(df)
        
        # 2. 防資料洩漏檢查
        if cutoff_timestamp and df["timestamp"].max() > cutoff_timestamp:
            raise DataLeakageError(f"Input contains data after cutoff {cutoff_timestamp}")
        
        # 3. 依序產生特徵（順序很重要）
        df = self._generate_physics_features(df)
        df = self._generate_time_features(df)
        df = self._generate_stats_features(df)  # 必須在最後，因為依賴前面產生的特徵
        
        return df
```

### Phase 2: 物理特徵引擎 (預估 1 天)

#### Step 2.1: 建立獨立物理公式庫
**檔案**: `src/utils/physics.py`（從 Cleaner 遷移並強化）

```python
import polars as pl

def calculate_wet_bulb_temp(
    t_db: pl.Series,      # 乾球溫度 (°C)
    rh: pl.Series,        # 相對濕度 (%)
    pressure: pl.Series,  # 大氣壓 (hPa)
    temp_range: Tuple[float, float] = (-40, 60),
    rh_range: Tuple[float, float] = (0, 100)
) -> pl.Series:
    """
    計算濕球溫度 (Wet Bulb Temperature)
    
    邊界處理：
    - 輸入超出物理範圍時回傳 Null（非拋出例外）
    - 使用 ASHRAE 標準公式或 psychrolib
    """
    # 邊界檢查
    valid_mask = (
        t_db.is_between(temp_range[0], temp_range[1]) & 
        rh.is_between(rh_range[0], rh_range[1])
    )
    
    # 計算（向量化）
    result = _ashrae_wet_bulb_formula(t_db, rh, pressure)
    
    # 無效值保護
    return pl.when(valid_mask).then(result).otherwise(None)

def calculate_enthalpy(t_db: pl.Series, w: pl.Series) -> pl.Series:
    """計算焓值 (kJ/kg)，輸入：溫度(°C)、含濕量(kg/kg)"""
    ...
```

#### Step 2.2: 實作物理特徵轉換層
**邏輯**:
- 從 `feature_mapping` 識別 `physical_type` 為 `temperature` 與 `humidity` 的欄位對
- 自動配對計算（如 `dry_bulb_temp_ch1` + `relative_humidity_ch1` → `wet_bulb_temp_ch1`）
- **命名規範**: `{location}_wet_bulb_temp_physics`, `{location}_enthalpy_physics`

### Phase 3: 時間與統計特徵 (預估 1.5 天)

#### Step 3.1: 時間特徵與週期性編碼

```python
def _generate_time_features(self, df: pl.DataFrame) -> pl.DataFrame:
    """產生時間特徵與週期性編碼"""
    # 基礎時間元件
    df = df.with_columns([
        pl.col("timestamp").dt.hour().alias("hour_time"),
        pl.col("timestamp").dt.weekday().alias("day_of_week_time"),
        pl.col("timestamp").dt.month().alias("month_time"),
        (pl.col("timestamp").dt.weekday() >= 5).alias("is_weekend_time")
    ])
    
    # 週期性編碼（解決 23:00 與 00:00 距離問題）
    if self.config.time_features.cyclical_encoding:
        df = df.with_columns([
            (2 * np.pi * pl.col("hour_time") / 24).sin().alias("hour_sin_time"),
            (2 * np.pi * pl.col("hour_time") / 24).cos().alias("hour_cos_time"),
            (2 * np.pi * pl.col("day_of_week_time") / 7).sin().alias("dow_sin_time"),
            (2 * np.pi * pl.col("day_of_week_time") / 7).cos().alias("dow_cos_time")
        ])
    
    return df
```

#### Step 3.2: Lag 與 Rolling 特徵（含安全機制）

```python
def _generate_stats_features(self, df: pl.DataFrame) -> pl.DataFrame:
    """
    產生統計特徵，嚴格遵守記憶體安全限制
    """
    # 取得可進行統計運算的數值欄位（排除 timestamp, quality_flags 等）
    numeric_cols = [
        c for c in df.columns 
        if get_feature_meta(c).enable_lag or get_feature_meta(c).enable_rolling
    ]
    
    expressions = []
    
    # Lag 特徵（延遲）
    for col in numeric_cols:
        for lag in self.config.stats_features.lag_intervals:
            expressions.append(
                pl.col(col).shift(lag).alias(f"{col}_lag_{lag}")
            )
    
    # Rolling 特徵（滾動統計）
    for col in numeric_cols:
        for window in self.config.stats_features.rolling_windows:
            # 安全檢查：視窗大小不得超過資料長度的 50%
            if window > len(df) * 0.5:
                logger.warning(f"Skipping rolling window {window} for {col}: exceeds 50% of data length")
                continue
                
            for agg in self.config.stats_features.aggregations:
                expr = getattr(pl.col(col).rolling_mean(window), agg)()
                expressions.append(
                    expr.alias(f"{col}_roll{agg}_{window}")
                )
    
    return df.with_columns(expressions)
```

### Phase 4: Quality Flags 處理策略

依據 `input_contract.quality_flags_handling` 執行：

```python
def _handle_quality_flags(self, df: pl.DataFrame) -> pl.DataFrame:
    strategy = self.config.input_contract.quality_flags_handling
    
    if strategy == "drop":
        # 刪除任何有標記的列（保守策略）
        has_flags = pl.col("quality_flags").list.len() > 0
        return df.filter(~has_flags)
    
    elif strategy == "onehot":
        # 將標記拆解為 One-Hot 特徵（推薦，保留資訊供模型學習）
        all_flags = ["FROZEN", "HEAT_IMBALANCE", "AFFINITY_VIOLATION", "OUTLIER"]
        for flag in all_flags:
            df = df.with_columns(
                pl.col("quality_flags").list.contains(flag).alias(f"is_{flag.lower()}_flag")
            )
        return df
    
    elif strategy == "ignore":
        # 忽略，不處理（快速但不建議）
        return df
```

---

## 4. 驗證與測試計畫

### 4.1 單元測試（強化版）

| 測試案例 | 驗證內容 | 通過標準 |
|:---|:---|:---:|
| **Case A (Physics Accuracy)** | 輸入 30°C / 50% RH，驗證濕球溫度計算 | 誤差 < 0.1°C（與 ASHRAE 表格比對） |
| **Case B (Cyclical Encoding)** | 驗證 23:00 的 `hour_sin/cos` 與 01:00 是否鄰近 | 向量距離 < 0.5（cos/sin 平面距離） |
| **Case C (Temporal Leakage)** | 驗證 Lag 特徵未參照未來資料 | `cutoff_timestamp` 後的資料被正確排除 |
| **Case D (Memory Safety)** | 測試 100 萬筆資料 + 大視窗 Rolling | 記憶體峰值 < 原始 DataFrame 的 150% |
| **Case E (Temporal Integrity)** | 測試時間序列有缺失時 Lag 行為 | 空缺處正確標記為 Null，無錯誤對齊 |
| **Case F (Idempotency)** | 同一批資料執行兩次 `transform()` | 結果 Bit-wise 完全一致 |
| **Case G (Null Propagation)** | 輸入含 Null，驗證特徵計算行為 | Null 不傳播（除依賴 Null 的特徵外），且不拋出例外 |
| **Case H (Quality Flags One-Hot)** | 驗證 quality_flags 拆解正確 | `is_frozen_flag` 等欄位正確標記 0/1 |

### 4.2 整合驗證

- **與 Cleaner v2.0 整合**：使用 Cleaner 輸出（含 `quality_flags`）作為輸入，驗證整條 Pipeline 記憶體使用 < 8GB（Cleaner 4GB + Feature Engineer 4GB）
- **與 Model 銜接**：驗證產生的特徵矩陣可被 XGBoost 直接讀取（無 Null、無無限值、無字串欄位殘留）

---

## 5. 風險評估與緩解

| 風險 | 嚴重度 | 緩解措施（已整合至設計） |
|:---|:---:|:---|
| **維度爆炸 (Feature Explosion)** | 🔴 Critical | `max_rolling_window_points: 1000` 強制限制，超過拋出 `ConfigurationError` |
| **Temporal Leakage** | 🔴 High | 時間連續性驗證 + `cutoff_timestamp` 防護機制 |
| **記憶體 OOM** | 🔴 High | 記憶體預檢（Pre-flight check），估算超過 150% 原始資料時改用 Streaming Mode |
| **Input Contract 違反** | 🟠 High | `_validate_input()` 嚴格檢查，違反時拋出明確錯誤訊息（而非神秘崩潰） |
| **物理計算邊界錯誤** | 🟠 Medium | 無效值回傳 Null（非拋出例外），避免整批失敗 |
| **特徵命名衝突** | 🟡 Medium | 嚴格命名規範 `{col}_{transform}_{param}`，若欄位已存在則拋出 `DuplicateFeatureError` |

---

## 6. 交付產物清單

1. `src/etl/feature_engineer.py`: 核心程式碼（含防禦機制與驗證）
2. `src/etl/config_models.py`: 擴充的 Pydantic 配置模型（與 Cleaner PRD 共用）
3. `src/utils/physics.py`: 獨立物理公式庫（從 Cleaner 遷移，含邊界檢查）
4. `tests/test_feature_engineer.py`: 涵蓋 Case A~H 的完整測試
5. `tests/test_physics_utils.py`: 物理公式準確性測試（與 ASHRAE 標準值比對）
6. `config/settings.yaml`: 更新範本（含 `etl_pipeline.feature_engineer` 區塊）
7. `docs/feature_engineering_guide.md`: 給 Data Scientist 的使用指南（如何配置 Lag/Rolling）

---

## 7. 與 Cleaner PRD 的協作檢查清單

在開始 Phase 2（物理特徵）前，請與 Cleaner 負責人確認：

- [ ] Cleaner v2.0 輸出是否保證 `timestamp` 欄位存在且為 UTC？
- [ ] `quality_flags` 欄位格式是否為 `List[str]`（Polars `pl.List(pl.Utf8)`）？
- [ ] Cleaner 的 `fill_strategy` 是否會產生時間空缺？若有，Feature Engineer 應如何處理（`upsample` 或保留 Null）？
- [ ] 兩者的 `settings.yaml` 配置路徑是否一致（`etl_pipeline.cleaner` + `etl_pipeline.feature_engineer`）？
- [ ] 記憶體預算如何分配？建議 Cleaner:Feature Engineer = 4GB:4GB，總計 8GB 上限

---

**審閱重點**：請特別確認 **Step 3.2 的 Rolling Window 安全限制** 與 **Quality Flags 處理策略** 是否符合下游 XGBoost 模型的期望（是否需要 `is_frozen` 作為特徵，還是直接丟棄異常資料）。
```
