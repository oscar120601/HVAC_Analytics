# HVAC 資料清洗與視覺化儀表板 - 執行手冊 (Runbook)

## 1. 專案啟動 (Getting Started)

### 前置需求
確保您已安裝 Python 3.8+ 與必要的套件。
```bash
cd HVAC_Cleaning_Visualization
pip install -r requirements.txt
# 或 python3 -m pip install -r requirements.txt
```

### 啟動應用程式
在終端機執行以下指令：
```bash
streamlit run app.py
```
啟動後，瀏覽器應會自動打開 `http://localhost:8501`。

## 2. 功能操作指南

### 步驟 1: 選擇專案資料夾 (Select Project)
1.  進入儀表板後，左側側邊欄上方會顯示「**專案設定**」。
2.  在「**選擇專案資料夾**」下拉選單中，選擇您要分析的案場 (例如：`Farglory_O3` 或 `kmuh`)。
3.  系統會自動載入該資料夾下的所有 CSV 檔案並進行清洗。

### 步驟 2: 檢視數據與圖表 (Visualize)
-   **趨勢分析**：檢視環境溫度、總耗電量與個別空調箱 (AHU) 的運作趨勢。
-   **關聯性分析**：探索外氣溫度對總耗電量的影響。
-   **原始數據**：檢視清洗後的表格數據與缺失值狀況。

### 步驟 3: 匯出清洗後的資料 (Export)
1.  確認目前顯示的數據與篩選範圍是您想要的。
2.  在左側側邊欄下方，找到「**資料匯出**」區塊。
3.  點擊「**下載清洗後的資料 (CSV)**」按鈕。
4.  瀏覽器將下載一個名為 `{專案名稱}_cleaned_data.csv` 的檔案，此檔案已包含：
    -   統一的時間戳記索引。
    -   清洗後的傳感器數值。
    -   計算出的衍生特徵 (如露點溫度、總耗電量)。

## 3. 新增資料 (Adding New Data)

若您有新的案場數據需要分析：
1.  在 `data/` 目錄下建立一個新的資料夾 (例如 `data/New_Building/`)。
2.  將符合格式的 CSV 檔案放入該資料夾中。
3.  重新整理網頁 (F5)，新的資料夾名稱將自動出現在「選擇專案資料夾」選單中。

## 4. 客製化設定 (Customization)

### 設定檔 `config.json`
每個專案資料夾下都應包含一個 `config.json` 檔案，用於告訴程式該如何識別您的欄位命名規則。
若您新增了一個新的案場 `data/New_Site/`，請複製現有的 `config.json` 到該目錄並修改：

```json
{
    "tag_keywords": {
        "out_air_temp": ["OAT", "外氣溫度"],      // 系統會尋找包含這些關鍵字的欄位
        "out_air_humidity": ["OAH", "外氣濕度"],
        "power_kwh": ["KWH", "總用電"],
        "valve_opening": [".CV", "閥門"],
        "supply_air_temp": [".SAT", "送風溫"]
    }
}
```

## 5. 常見問題

**Q: 下拉選單找不到我的新資料夾？**
A: 請確保該資料夾位於 `data/` 目錄下，且不是以 `.` 開頭的隱藏資料夾。

**Q: 載入時出現錯誤 "No data found or failed to parse"？**
A: 請檢查資料夾內的 CSV 檔案格式是否符合 `data_parser.py` 的預期 (需包含 "Point_X" Metadata 標籤)。
