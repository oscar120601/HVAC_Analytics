# 清洗器優化評估與重構建議 (Cleaner Refactoring Proposal)

**日期:** 2026-02-12
**目標模組:** [cleaner.py](file:///d:/12.任務/HVAC-1/src/etl/cleaner.py)
**文件狀態:** 草案 (Draft)

---

## 1. 嚴謹性審查與問題分析

經過對 `DataCleaner` 程式碼的深度審查，目前實作存在多項**架構性缺陷**與**邏輯漏洞**，無法滿足生產環境與多案場擴展的需求。以下是關鍵問題分析：

| 編號 | 問題分類 | 問題描述 | 嚴重程度 | 潛在後果 |
|:---:|:---:|:---|:---:|:---|
| C1 | **單位依賴 (Unit Dependency)** | `validate_heat_balance` 強制使用英制公式 `(GPM * dT) / 24`，完全未考慮公制單位 (LPM, °C)。 | **Critical** | 非美規案場的熱平衡驗證將全數失敗或誤判。 |
| C2 | **邏輯脆弱 (Fragile Logic)** | 重採樣 (Resampling) 的聚合邏輯依賴 `endswith("KWH")` 等硬編碼後綴。 | **High** | 若欄位命名不符慣例 (如 `Power_Consumption`)，將錯誤地使用 `mean()` 導致計數器數據損毀。 |
| C3 | **精度不足 (Low Accuracy)** | 濕球溫度計算使用 Magnus-Tetens 簡化近似公式，誤差隨極端條件放達。 | **Medium** | 影響依賴焓值 (Enthalpy) 的精密節能計算準確度。 |
| C4 | **循環論證 (Circular Logic)** | 親和律驗證 (Affinity Law) 以「當前資料集的流量/功率中位數」為基準。 | **High** | 若整個資料集都是異常運轉數據 (如變頻器設定錯誤)，驗證機制將失效並「自我合理化」。 |
| C5 | **缺乏配置 (Lack of Config)** | COP 範圍、穩定態判定窗口、容許誤差等閾值皆為硬編碼預設值。 | **Medium** | 無法針對不同冰機型號或案場特性進行微調。 |
| C6 | **副作用 (Side Effects)** | `detect_frozen_data` 等方法產生大量中間欄位 (`_frozen`, `_flag`) 污染 DataFrame。 | **Low** | 增加記憶體消耗，混淆後續特徵選取。 |

---

## 2. 重構目標 (To-Be State)

將 `DataCleaner` 轉型為**單元感知 (Unit-Aware)**、**配置驅動 (Configuration-Driven)** 且**無狀態副作用**的清洗引擎。

### 核心原則
1.  **顯式優於隱式**：聚合規則與驗證邏輯應由配置檔定義，而非依賴欄位名稱猜測。
2.  **物理一致性**：所有物理計算需先標準化單位 (SI制) 再執行。
3.  **可追溯性**：清洗過程應產生詳細的品質報告 (Quality Report)，而非僅僅丟棄資料。

---

## 3. 分階段重構計畫

### Phase 1: 基礎架構與配置化 (Foundation)

#### Task 1.1: 引入清洗配置 Schema
建立 `CleanerConfig` (Pydantic)，取代散落在 `__init__` 的參數：
- **聚合規則**: 定義哪些欄位用 `sum`, `max`, `last`, `mean`。
- **物理參數**: 定義該案場的單位系統 (Metric/Imperial)、冰機額定規格 (Design Capacity)。
- **閾值設定**: COP 合理範圍、穩定態判定標準 (ex: 5% / 15min)。

#### Task 1.2: 標準化重採樣引擎
重寫 `resample_to_intervals`，移除硬編碼的 `if/else` 判斷，改由配置檔驅動聚合策略。
- 若無配置，則僅對明確的數值型欄位做 `mean`，字串型做 `first`，避免對不明欄位胡亂運算。

### Phase 2: 物理邏輯增強 (Physics & Validation)

#### Task 2.1: 單元感知的熱平衡驗證
重構 `validate_heat_balance`：
- 支援單位輸入：`flow_unit` (LPM/GPM), `temp_unit` (C/F), `power_unit` (RT/kW)。
- 內部統一轉為 SI 單位計算：$Q = \dot{m} \cdot C_p \cdot \Delta T$。
- 引入水的比熱 ($C_p$) 修正因子 (依溫度變動)。

#### Task 2.2: 基準線驅動的親和律驗證
重構 `validate_affinity_laws`：
- **移除中位數基準**。
- 改為接受「額定工況點」(Design Point: $Hz_{ref}, kW_{ref}$) 作為基準。
- 驗證公式：$kW_{act} \approx kW_{ref} \cdot (\frac{Hz_{act}}{Hz_{ref}})^3$。

#### Task 2.3: 精密濕球溫度計算
- 引入 `psychrolib` 或實作 ASHRAE 標準公式，替換現有的簡化公式。
- 增加輸入邊界檢查 (RH > 100% 或 T < -273°C 的異常處理)。

### Phase 3: 資料品質治理 (Data Governance)

#### Task 3.1: 無副作用的標記機制
- 清洗方法不再直接修改原始 DataFrame 增加垃圾欄位。
- 改為回傳 `QualityReport` 物件或僅增加一個 `quality_flags` 結構化欄位 (Bitmask 或 List)，標記每一列的問題 (e.g., `["FROZEN", "UNBALANCED"]`)。

#### Task 3.2: 異常處理策略
- 實作策略模式：
  - `Strategy.DROP`: 直接丟棄 (現有邏輯)。
  - `Strategy.FLAG_ONLY`: 保留但標記 (適用於訓練資料不足時)。
  - `Strategy.IMPUTE`: 插補 (線性/前向填充)。

---

## 4. 程式碼示範 (Refactoring Preview)

**重構後的介面概念：**

```python
class CleanerConfig(BaseModel):
    units: UnitSystem = UnitSystem.METRIC  # or IMPERIAL
    aggregation_rules: Dict[str, str] = {
        "*_KWH": "last",
        "*_STATUS": "max",
        "default": "mean"
    }
    limits: OperationalLimits = OperationalLimits(cop_min=1.5, cop_max=10.0)

class PhysicsCleaner:
    def __init__(self, config: CleanerConfig):
        self.config = config

    def validate_heat_balance(self, df: pl.DataFrame) -> pl.Series:
        # 1. 自動轉換單位至 SI
        # 2. 執行物理計算
        # 3. 回傳 Boolean Series (Valid/Invalid)，不汙染原 DF
        pass
```

## 5. 建議行動

1. **批准此評估方向**：確認是否同意針對上述 C1-C5 問題進行修復。
2. **建立測試案例**：在修改程式碼前，先建立一個包含「公制單位」與「異常親和律」的測試資料集，證明目前程式碼會失敗 (Test-Driven Fix)。
3. **執行重構**：優先處理 **Phase 2 (物理邏輯)**，解決最嚴重的單位錯誤問題。
