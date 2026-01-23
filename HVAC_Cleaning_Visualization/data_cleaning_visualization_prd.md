# 產品需求文件 (PRD)
## HVAC 資料清洗與趨勢視覺化 Dashbaord

> [!NOTE]
> 本文件已根據實作階段的發現進行更新 (2025-01-23)。
> 專案位置：`HVAC_Cleaning_Visualization/`

## 1. 專案背景
本專案目標是整合來自不同子系統 (AHU, 電力, 環境) 的原始 CSV 數據，建立自動化的清洗與視覺化流程。主要重點是解決目前數據分散、格式不一致的問題，並提供互動式分析工具以識別耗能異常與操作關聯。

## 2. 資料來源
系統目前支援自動解析與合併以下類型的監控數據 (位於 `data/Farglory_O3/`)：

1.  **AHU 運轉數據** (`adv_ahu_*.csv`)
    -   **冰水閥開度 (Valve Opening, %)**：標籤關鍵字 `.CV`
    -   **送風溫度 (Supply Air Temp, °C)**：標籤關鍵字 `.SAT`
2.  **電力數據** (`adv_air_kwh_*.csv`)
    -   **用電量 (Power Consumption, kWh)**：標籤關鍵字 `.KWH`
3.  **環境與水溫數據** (`adv_air_temp_*.csv`)
    -   **外氣溫度 (OAT, °C)**
    -   **外氣濕度 (OAH, %)**
    -   **冰水管溫度 (CHW, °C)**
4.  **流量計 (Flow Meter)** (*待整合*)
    -   預留欄位解析 (LPM/GPM)。目前尚未在檔案中偵測到明確數據，一旦提供對應 CSV 即可透過標籤關鍵字整合。

## 3. 功能實作細節

### 3.1 資料解析與整合 (Data Parsing)
-   **格式處理**：針對此案特殊的 "Metadata Tag Mapping + Pre-pivoted Data" CSV 格式開發了專用解析器 (`data_parser.py`)。
-   **自動合併**：依據 `timestamp` 自動對齊上述三種不同來源的檔案，產生單一 Master Dataset。

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

### 3.4 視覺化 (Visualization)
已使用 **Streamlit** 實作互動式儀表板 (`app.py`)：
1.  **時間序列分析**：
    -   可互動縮放的折線圖。
    -   支援多軸顯示：同時檢視 溫度 (左軸) vs 閥門開度/濕度 (右軸)。
2.  **關聯性分析 (Correlation)**：
    -   **外氣 vs 負載**：散佈圖呈現 `Outer Air Temp` vs `Total Power`。
    -   **流量 vs 負載**：(預留) 散佈圖呈現 `Flow` vs `Power`。
3.  **原始資料檢視**：提供清洗後的數據表格與缺失值熱圖 (Heatmap)。

## 4. 系統需求
-   **語言**：Python 3.8+
-   **核心套件**：
    -   `pandas` (數據處理)
    -   `streamlit` (Web App 框架)
    -   `plotly` (互動式圖表)
    -   `numpy` (數值計算)

## 5. 後續優化建議
-   **流量數據整合**：取得明確的流量計 CSV 檔案後，確認其標籤命名規則並更新 parser。
-   **異常警報**：可設定規則 (例如：閥門全開但溫度未降) 自動標記異常時段。
