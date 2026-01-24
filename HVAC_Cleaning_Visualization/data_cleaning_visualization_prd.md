# 產品需求文件 (PRD) - V2
## HVAC 資料清洗與趨勢視覺化儀表板 (Dashboard)

> [!NOTE]
> **V2 更新 (2026-01-24)**：新增機器學習功能模組（特徵標注、異常偵測、能耗預測）
> 
> V1 更新 (2025-01-23)：翻譯與基礎實作階段
> 
> 專案位置：`HVAC_Cleaning_Visualization/`

## 1. 專案背景
本專案目標是整合來自不同子系統 (AHU, 電力, 環境) 的原始 CSV 數據，建立自動化的清洗與視覺化流程。主要重點是解決目前數據分散、格式不一致的問題，並提供互動式分析工具 (`HVAC 資料清洗與視覺化儀表板`) 以識別耗能異常與操作關聯。

**V2 新增目標**：透過機器學習技術，實現自動化異常偵測與能耗預測功能。

## 2. 資料來源
系統目前支援自動解析與合併以下類型的監控數據 (位於 `data/Farglory_O3/`)：

1.  **AHU 運轉數據** (`adv_ahu_*.csv`)
2.  **電力數據** (`adv_air_kwh_*.csv`)
3.  **環境與水溫數據** (`adv_air_temp_*.csv`)

### 2.1 客製化資料對應 (Configurable Mapping)
為支援不同案場（不同建築物）的感測器命名規則差異，每個專案資料夾下皆包含一個 `config.json` 設定檔，使用者可定義該案場的關鍵字對應：
-   `power_kwh`: 用電量欄位關鍵字 (如 `.KWH`, `MMCB.KW`)
-   `out_air_temp`: 外氣溫度 (如 `OAT`, `MMCB.TA`)
-   `out_air_humidity`: 外氣濕度 (如 `OAH`, `MMCB.RH`)
-   `valve_opening`: 閥門開度 (如 `.CV`)
-   `supply_air_temp`: 送風溫度 (如 `.SAT`)

## 3. 功能實作細節

### 3.1 資料解析與整合 (Data Parsing)
-   **格式處理**：針對此案特殊的 "Metadata Tag Mapping + Pre-pivoted Data" CSV 格式開發了專用解析器 (`data_parser.py`)。
-   **自動合併 (Robust Merge)**：
    -   採用 **堆疊 (Stacking) + 聚合 (Aggregation)** 策略。
    -   首先讀取並連接 (Concat) 所有 CSV 檔案，不依賴特定檔名規則。
    -   接著依據時間戳記 (Timestamp) 進行聚合與除重，確保即使多個檔案包含相同的時間區段或欄位，也能正確整合為單一主數據集 (Master Dataset)。

### 3.2 資料清洗 (Cleaning)
-   **缺失值**：自動識別並轉換 `No Data` 字串為 `NaN`。
-   **異常過濾**：
    -   濕度 > 100% 或 < 0% 視為無效。
    -   閥門開度 > 100% 視為無效。

### 3.3 特徵工程 (Feature Engineering)
-   **空氣性質計算**：
    -   利用 `OAT` + `OAH` 計算 **露點溫度 (Dew Point)** 與 **濕球溫度 (Wet Bulb)**。
-   **總耗能計算**：
    -   自動加總所有偵測到的 `.KWH` 欄位，計算 `Derived_Total_Power`。
-   **[V2 新增] 機器學習特徵**：
    -   時間特徵：`hour`, `dayofweek`, `is_weekend`, `month`
    -   滾動統計：`rolling_mean_1h`, `rolling_std_1h`, `rolling_mean_6h`

### 3.4 視覺化 (Visualization)
已使用 **Streamlit** 實作互動式儀表板 (`app.py`)，**介面全繁體中文**：
1.  **多專案資料選擇**：
    -   自動偵測 `data/` 下的所有資料夾 (例如 `Farglory_O3`, `kmuh`)。
    -   使用者可於側邊欄切換不同專案，即時載入並清洗對應數據。
2.  **資料匯出功能**：
    -   側邊欄提供「下載清洗後的資料 (CSV)」按鈕，可將處理後的 Master Dataset 匯出。
3.  **時間序列趨勢 (Time Series Trends)**：
    -   可互動縮放的折線圖。
    -   支援多軸顯示：同時檢視 溫度 (左軸) vs 閥門開度/濕度 (右軸)。
    -   圖表：**外氣溫度 / 濕度 / 濕球溫度**、**總耗電量**、**空調箱 (AHU) 效能**。
4.  **關聯性分析 (Correlation Analysis)**：
    -   **外氣 vs 負載**：散佈圖呈現 `耗電量` vs `外氣溫度`。
    -   **流量 vs 負載**：(預留) 散佈圖呈現 `流量` vs `耗電量`。
5.  **原始數據檢視 (Raw Data)**：提供清洗後的數據表格與 **缺失值熱圖 (Missing Data Heatmap)**。

### 3.5 [V2 新增] 機器學習功能 (Machine Learning)
新增「機器學習」Tab，包含以下三大功能：

#### 3.5.1 特徵標注 (Feature Labeling)
-   **功能**：手動標記時間區段的數據狀態
-   **標籤類型**：
    -   `normal` - 正常運作
    -   `anomaly` - 異常
    -   `maintenance` - 維護中
    -   `unknown` - 未知
-   **儲存格式**：JSON 檔案 (`labels/{project}_labels.json`)
-   **用途**：建立標注資料集以供後續監督式學習模型訓練

#### 3.5.2 異常偵測 (Anomaly Detection)
-   **演算法**：Isolation Forest（非監督式學習）
-   **可調參數**：
    -   `contamination` (異常比例): 0.01 ~ 0.20
-   **輸出**：
    -   `is_anomaly` 欄位標記
    -   `anomaly_score` 異常分數
    -   異常時段列表與視覺化圖表

#### 3.5.3 能耗預測 (Energy Prediction)
-   **演算法**：Random Forest Regressor
-   **輸入特徵**：
    -   環境參數 (外氣溫度、濕度)
    -   時間特徵 (小時、星期、週末)
    -   滾動統計特徵
-   **輸出**：
    -   `predicted_power` 預測能耗
    -   模型 R² 分數
    -   特徵重要性排名
-   **模型儲存**：支援匯出 pickle 格式 (`models/`)

## 4. 系統架構

```
HVAC_Cleaning_Visualization/
├── app.py                 # Streamlit 主程式
├── data_parser.py         # CSV 解析器
├── data_pipeline.py       # 資料清洗 & 特徵工程
├── ml_pipeline.py         # [V2] 機器學習模組
├── requirements.txt       # 套件需求
├── data/                  # 原始資料
│   ├── Farglory_O3/
│   └── kmuh/
├── labels/                # [V2] 標籤儲存
└── models/                # [V2] 模型儲存
```

## 5. 系統需求
-   **語言**：Python 3.8+
-   **核心套件**：
    -   `pandas` (數據處理)
    -   `streamlit` (Web App 框架)
    -   `plotly` (互動式圖表)
    -   `numpy` (數值計算)
    -   `scikit-learn` (機器學習) **[V2 新增]**
    -   `xgboost` (進階機器學習) **[V2 新增]**

## 6. 後續優化建議
-   **流量數據整合**：取得明確的流量計 CSV 檔案後，確認其標籤命名規則並更新 parser。
-   ~~**異常警報**：可設定規則 (例如：閥門全開但溫度未降) 自動標記異常時段。~~ ✅ 已於 V2 實作
-   **[V2 建議] 模型自動化訓練**：定期重新訓練預測模型以適應季節變化。
-   **[V2 建議] 即時異常通知**：整合 Email/LINE 通知系統，當偵測到異常時自動發送警報。
-   **[V2 建議] 深度學習模型**：考慮使用 LSTM/Transformer 進行時間序列預測。
