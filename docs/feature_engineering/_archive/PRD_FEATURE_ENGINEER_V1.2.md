# PRD v1.2: 特徵工程強健性實作指南 (Feature Engineering Implementation Guide)

**文件版本:** v1.2  
**日期:** 2026-02-12  
**負責人:** Oscar Chang  
**目標模組:** `src/etl/feature_engineer.py`  
**相依模組:** `src/etl/cleaner.py` (v2.0+), `src/utils/physics.py`  
**預估工時:** 3 ~ 4 個工程天（含整合測試）

---

## 1. 執行總綱與設計原則

### 1.1 核心職責
本模組專注於 **「加法與創造」**，嚴格禁止執行資料清洗或過濾。所有輸入資料必須先經過 `DataCleaner` 處理。

**設計原則：**
1. **防禦式設計**：即使 Cleaner 輸出異常（含 Null、空缺），仍不拋出致命錯誤
2. **冪等性 (Idempotency)**：相同輸入執行多次，輸出必須完全一致
3. **記憶體安全**：V1.0 明確鎖定 **In-Memory 批次處理**（但介面預留 LazyFrame 彈性）
4. **防 Data Leakage**：所有 Rolling/Lag 特徵嚴格排除「當前時間點」

### 1.2 輸入輸出契約（Input/Output Contract）

```python
class FeatureEngineerInputContract:
    required_columns: List[str] = ["timestamp"]
    expected_frequency: str = "15min"
    timestamp_tz: str = "UTC"
    quality_flags_handling: Literal["drop", "onehot", "ignore"] = "onehot"
    
    # 【新增】資料洩漏防護檢查
    strict_temporal_integrity: bool = True  # 若 True，發現未來資料時拋出例外

class FeatureEngineerOutputContract:
    feature_naming_convention: str = "{original_col}_{transformation}_{parameters}"
    null_strategy: str = "propagate_with_flag"
    
    # 【新增】時序正確性保證
    temporal_consistency: str = "所有 Lag/Rolling 特徵僅使用過去資料（不包含當前點）"
```

### 1.3 功能範圍

| 範圍 | 包含項目 (In-Scope) | 排除項目 (Out-of-Scope) |
|:---|:---|:---|
| **處理模式** | **V1.0 僅支援 In-Memory**（pl.DataFrame）<br>介面預留 pl.LazyFrame 相容性 | V1.0 不支援 Streaming Mode<br>（記憶體不足時應改用分批讀取，非 LazyFrame） |
| **P1 物理特徵** | 濕球溫度、焓值 | 單位轉換（由 Cleaner 處理） |
| **P2 統計特徵** | Lag（延遲）、Rolling（滾動統計）<br>【強制】排除當前點（closed='left'） | 複雜統計（EWM） |
| **P3 互動特徵** | Out-of-Scope | 非線性交互項 |

---

## 2. 系統架構與配置

### 2.1 【修正】統一配置檔結構（支援 Multi-Asset）

```yaml
# config/settings.yaml
etl_pipeline:
  feature_engineer:
    schema_version: "1.2"
    
    # 【新增】處理模式聲明
    execution_mode: "in_memory"  # v1.2 僅支援 in_memory，保留欄位供 v2.0 擴充
    
    input_contract:
      quality_flags_handling: "onehot"
      strict_temporal_integrity: true
      
    # 【優化】Multi-Asset 群組策略（取代逐一列舉）
    stats_features:
      enabled: true
      
      # 方案：以 physical_type 自動匹配，無需列舉欄位名稱
      group_policies:
        - apply_to_types: ["chiller_load", "cooling_tower_load"]
          rules:
            lag_intervals: [1, 4]      # 15min, 1hr
            rolling_windows: [4, 96]    # 1hr, 24hr（以區間數計，非絕對時間）
            aggregations: ["mean", "std"]
            max_window_points: 1000     # 安全限制
            
        - apply_to_types: ["power_usage"]
          rules:
            lag_intervals: [1]
            rolling_windows: [4]
            aggregations: ["mean", "max"]
            
      # 例外處理：特定欄位覆寫（可選）
      column_overrides:
        chiller_1_load:  # 若某台冰機需要特殊處理
          lag_intervals: [1, 2, 4]
          
    physics_features:
      enabled: true
      library: "psychrolib"
      apply_to_types: ["dry_bulb_temp", "relative_humidity"]  # 自動配對計算濕球溫度
      
    time_features:
      enabled: true
      cyclical_encoding: true
      components: ["hour", "day_of_week", "month", "is_weekend"]
```

### 2.2 【新增】Group Policy 解析邏輯

```python
# src/etl/feature_engineer.py
def _resolve_group_policies(self, df: pl.DataFrame) -> Dict[str, StatsRule]:
    """
    將 group_policies 解析為具體欄位配置
    避免逐一列舉導致的 config 膨脹
    """
    resolved = {}
    for policy in self.config.stats_features.group_policies:
        target_cols = [
            col for col in df.columns 
            if get_feature_meta(col).physical_type in policy.apply_to_types
            and not get_feature_meta(col).is_target  # 排除目標變數
        ]
        for col in target_cols:
            resolved[col] = policy.rules
    return resolved
```

---

## 3. 分階段實作計畫

### Phase 1: 基礎架構（含 LazyFrame 介面預留）

#### Step 1.1: 配置模型（含 Group Policy）

```python
from pydantic import BaseModel, validator
from typing import Union

class StatsRule(BaseModel):
    lag_intervals: List[int]
    rolling_windows: List[int]
    aggregations: List[str]
    max_window_points: int = 1000
    
    @validator('rolling_windows')
    def check_window_size(cls, v, values):
        max_points = values.get('max_window_points', 1000)
        if any(x > max_points for x in v):
            raise ValueError(f"Rolling window exceeds limit of {max_points}")
        return v

class GroupPolicy(BaseModel):
    apply_to_types: List[str]  # 匹配 physical_type
    rules: StatsRule

class FeatureEngineeringConfig(BaseModel):
    schema_version: Literal["1.2"] = "1.2"
    execution_mode: Literal["in_memory"] = "in_memory"  # V1.2 鎖定
    input_contract: FeatureEngineerInputContract
    stats_features: dict  # 包含 group_policies 與 column_overrides
    physics_features: PhysicsConfig
    time_features: TimeConfig
```

#### Step 1.2: 模組骨架（【修正】介面支援 Union 類型）

```python
import polars as pl
from typing import Union, Optional

class FeatureEngineer:
    def __init__(self, config: FeatureEngineeringConfig):
        self.config = config
        
    def transform(
        self, 
        df: Union[pl.DataFrame, pl.LazyFrame],  # 【修正】預留 LazyFrame 彈性
        cutoff_timestamp: Optional[datetime] = None
    ) -> Union[pl.DataFrame, pl.LazyFrame]:
        """
        主入口方法
        
        V1.2 實作限制：
        - 若輸入為 LazyFrame，僅支援「讀取」操作，實際運算仍為 Eager（collect）
        - V2.0 可擴充為完整 Streaming 支援
        """
        # 若為 LazyFrame，先 collect（V1.2 限制）
        # V2.0 時可移除此限制，直接回傳 LazyFrame
        if isinstance(df, pl.LazyFrame):
            df = df.collect()
            
        # 1. 輸入驗證（含時間連續性檢查）
        df = self._validate_input(df)
        
        # 2. 防 Data Leakage 檢查
        if cutoff_timestamp and df["timestamp"].max() > cutoff_timestamp:
            raise DataLeakageError(f"Input contains future data after {cutoff_timestamp}")
        
        # 3. 依序產生特徵
        df = self._generate_physics_features(df)
        df = self._generate_time_features(df)
        df = self._generate_stats_features(df)  # 【關鍵】使用 shift(1) 防 Data Leak
        
        return df
```

### Phase 2: 物理特徵引擎

#### Step 2.1: 物理公式庫（強化邊界檢查）

```python
# src/utils/physics.py
def calculate_wet_bulb_temp(
    t_db: pl.Series,
    rh: pl.Series,
    pressure: pl.Series,
    temp_range: Tuple[float, float] = (-40, 60),
    rh_range: Tuple[float, float] = (0, 100)
) -> pl.Series:
    """計算濕球溫度，無效值回傳 Null 而非拋出"""
    valid_mask = (
        t_db.is_between(temp_range[0], temp_range[1]) & 
        rh.is_between(rh_range[0], rh_range[1])
    )
    result = _ashrae_wet_bulb_formula(t_db, rh, pressure)
    return pl.when(valid_mask).then(result).otherwise(None)
```

#### Step 2.2: 自動配對 Multi-Asset 欄位

```python
def _generate_physics_features(self, df: pl.DataFrame) -> pl.DataFrame:
    """自動識別溫度/濕度欄位配對，支援多台設備"""
    # 透過 feature_mapping 識別所有 physical_type=temperature/humidity 的欄位
    temp_cols = [c for c in df.columns if get_meta(c).physical_type == "temperature"]
    rh_cols = [c for c in df.columns if get_meta(c).physical_type == "humidity"]
    
    # 自動配對（假設命名慣例：{location}_temp / {location}_rh）
    for temp_col in temp_cols:
        location = temp_col.replace("_temp", "")
        rh_col = f"{location}_rh"
        if rh_col in df.columns:
            df = df.with_columns([
                calculate_wet_bulb_temp(
                    pl.col(temp_col), 
                    pl.col(rh_col),
                    pl.lit(1013.25)  # 預設氣壓
                ).alias(f"{location}_wet_bulb_physics")
            ])
    return df
```

### Phase 3: 時間與統計特徵（【關鍵修正】防 Data Leakage）

#### Step 3.1: 時間特徵（維持不變）

```python
def _generate_time_features(self, df: pl.DataFrame) -> pl.DataFrame:
    df = df.with_columns([
        pl.col("timestamp").dt.hour().alias("hour_time"),
        pl.col("timestamp").dt.weekday().alias("day_of_week_time"),
        (pl.col("timestamp").dt.weekday() >= 5).alias("is_weekend_time"),
        (2 * np.pi * pl.col("timestamp").dt.hour() / 24).sin().alias("hour_sin_time"),
        (2 * np.pi * pl.col("timestamp").dt.hour() / 24).cos().alias("hour_cos_time"),
    ])
    return df
```

#### Step 3.2: 【修正】Lag 與 Rolling（強制排除當前點）

```python
def _generate_stats_features(self, df: pl.DataFrame) -> pl.DataFrame:
    """
    【關鍵修正】所有 Rolling 特徵必須排除「當前時間點」
    實作方式：先 shift(1) 再 rolling，確保僅使用「過去」資料
    """
    # 透過 Group Policy 解析目標欄位（支援 Multi-Asset）
    column_rules = self._resolve_group_policies(df)
    
    expressions = []
    
    for col, rules in column_rules.items():
        # Lag 特徵（延遲）- 本身即為過去資料，無需額外防護
        for lag in rules.lag_intervals:
            expressions.append(
                pl.col(col).shift(lag).alias(f"{col}_lag_{lag}")
            )
        
        # 【修正】Rolling 特徵：shift(1) 確保窗口從「上一個時間點」開始
        for window in rules.rolling_windows:
            # 安全檢查：視窗不得超過資料長度 50%
            if window > len(df) * 0.5:
                logger.warning(f"Skip rolling {window} for {col}: exceeds 50% data length")
                continue
            
            for agg in rules.aggregations:
                # 【關鍵】先 shift(1) 排除當前點，再做 rolling
                # 這確保「過去 24 小時」真的不包含「現在」
                expr = (
                    pl.col(col)
                    .shift(1)  # 【強制】先偏移，排除當前點
                    .rolling_mean(window) if agg == "mean" else
                    pl.col(col).shift(1).rolling_std(window) if agg == "std" else
                    pl.col(col).shift(1).rolling_min(window) if agg == "min" else
                    pl.col(col).shift(1).rolling_max(window)  # max
                )
                expressions.append(
                    expr.alias(f"{col}_roll{agg}_{window}")
                )
    
    return df.with_columns(expressions)
```

### Phase 4: Quality Flags 處理（維持不變）

```python
def _handle_quality_flags(self, df: pl.DataFrame) -> pl.DataFrame:
    strategy = self.config.input_contract.quality_flags_handling
    
    if strategy == "drop":
        has_flags = pl.col("quality_flags").list.len() > 0
        return df.filter(~has_flags)
    elif strategy == "onehot":
        all_flags = ["FROZEN", "HEAT_IMBALANCE", "AFFINITY_VIOLATION", "OUTLIER"]
        for flag in all_flags:
            df = df.with_columns(
                pl.col("quality_flags").list.contains(flag).alias(f"is_{flag.lower()}_flag")
            )
        return df
    else:  # ignore
        return df
```

---

## 4. 驗證與測試計畫（【新增】Data Leakage 測試）

| 測試案例 | 驗證內容 | 通過標準 |
|:---|:---|:---:|
| **Case A (Physics)** | 濕球溫度計算準確性 | 誤差 < 0.1°C |
| **Case B (Cyclical)** | 時間週期編碼正確性 | 23:00 與 01:00 向量距離 < 0.5 |
| **Case C (Temporal Leakage)** | Lag 不包含未來 | `cutoff_timestamp` 後資料被排除 |
| **Case D (Memory)** | 大資料量處理 | 記憶體 < 原始資料 150% |
| **Case E (Idempotency)** | 重複執行一致性 | Bit-wise 一致 |
| **Case F (Data Leakage - Rolling)**【新增】 | Rolling 不包含當前點 | 對於時間 T，特徵值僅使用 T-1, T-2... 資料 |
| **Case G (Multi-Asset)**【新增】 | Group Policy 解析 | 3 台冰機自動套用相同規則，config 無需重複 |
| **Case H (LazyFrame)**【新增】 | 介面相容性 | 輸入 LazyFrame 不拋出 TypeError（雖然會 collect） |

### 【新增】Data Leakage 測試範例

```python
def test_rolling_no_data_leakage():
    """驗證 Rolling 特徵不包含當前時間點"""
    # 建立測試資料：時間序列 1, 2, 3, 4, 5...
    df = pl.DataFrame({
        "timestamp": pl.date_range(datetime(2024,1,1), datetime(2024,1,2), interval="1h"),
        "value": range(25)  # 0, 1, 2, ..., 24
    })
    
    config = FeatureEngineeringConfig(
        stats_features={
            "group_policies": [{
                "apply_to_types": ["gauge"],
                "rules": {"lag_intervals": [], "rolling_windows": [3], "aggregations": ["mean"]}
            }]
        }
    )
    
    engineer = FeatureEngineer(config)
    result = engineer.transform(df)
    
    # 驗證：第 3 個時間點（index=2, value=2）的 rolling_mean_3
    # 若正確（不含當前點）：應為 (0 + 1) / 2 = 0.5（因為 shift(1) 後窗口為 [Null, 0, 1]）
    # 若錯誤（含當前點）：會是 (0 + 1 + 2) / 3 = 1.0
    row_3 = result.filter(pl.col("timestamp") == datetime(2024,1,1,2,0)).to_dict()
    assert row_3["value_rollmean_3"][0] == 0.5, "Data Leakage detected! Rolling includes current point."
```

---

## 5. 風險評估與緩解（更新）

| 風險 | 嚴重度 | 緩解措施（V1.2 設計） |
|:---|:---:|:---|
| **維度爆炸** | 🔴 Critical | `max_window_points: 1000` + Group Policy 集中管理 |
| **Temporal Leakage** | 🔴 High | **強制 `shift(1)` 邏輯**，測試 Case F 驗證 |
| **Streaming Mode 未定義** | 🟠 Medium | **明確聲明 V1.2 僅支援 In-Memory**，介面預留 LazyFrame |
| **Multi-Asset Config 膨脹** | 🟠 Medium | **Group Policy** 以 `apply_to_types` 取代逐一列舉 |
| **Input Contract 違反** | 🟠 Medium | `_validate_input()` 嚴格檢查 |
| **物理計算邊界錯誤** | 🟡 Medium | 無效值回傳 Null |

---

## 6. 與 Cleaner PRD 的協作檢查清單（更新）

在開始開發前，請與 Cleaner 負責人確認：

- [ ] Cleaner v2.0 輸出是否包含 `physical_type` 中繼資料（供 Group Policy 匹配）？
- [ ] `quality_flags` 格式是否為 `List[str]`？
- [ ] 兩者的 `timestamp` 是否皆為 UTC 且對齊方式一致（`alignment: "left"`）？
- [ ] **【新增】** Cleaner 是否保證輸出「無未來資料」？（Feature Engineer 會做二次檢查）
- [ ] **【新增】** 若案場有 3 台冰機，欄位命名是否遵循 `{location}_{type}` 慣例（如 `chiller_1_load`）？

---

## 7. 交付產物清單

1. `src/etl/feature_engineer.py`: 核心程式碼（含 `shift(1)` 防護與 Group Policy）
2. `src/etl/config_models.py`: 更新配置模型（`GroupPolicy`, `StatsRule`）
3. `src/utils/physics.py`: 物理公式庫（含邊界檢查）
4. `tests/test_feature_engineer.py`: 含 Case F (Data Leakage) 與 Case G (Multi-Asset)
5. `tests/test_data_leakage.py`: 【新增】專門驗證時序正確性的測試檔案
6. `config/settings.yaml`: 更新範本（示範 Group Policy 寫法）
7. `docs/feature_engineering_guide.md`: 更新說明（強調「過去資料-only」原則）
