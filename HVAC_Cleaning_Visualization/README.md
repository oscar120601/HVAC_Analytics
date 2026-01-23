# HVAC 資料清洗與視覺化 (HVAC Data Cleaning & Visualization)

本專案實作了一套資料管線，用於清洗、分析與視覺化來自建築自動化系統 (BAS) 的 HVAC 感測器數據。

## 功能特色
- **多來源資料整合**：自動合併來自不同子系統（空調箱 AHU、電力、環境）的 Pivot 格式 CSV 檔案。
- **資料清洗**：自動處理 "No Data" 標記、缺失值與異常值。
- **特徵工程**：計算露點 (Dew Point) 與 濕球溫度 (Wet Bulb Temperature)。
- **互動式儀表板**：基於 Streamlit 的視覺化介面，提供趨勢與相關性分析。

## 設定與執行

1.  **安裝相依套件**：
    ```bash
    pip install -r requirements.txt
    ```
    *(若出現 pip 指令錯誤，請參考下方「常見問題」章節)*

2.  **資料放置**：
    請確保您的原始 CSV 檔案位於 `data/Farglory_O3/` 資料夾內（或於 `data_parser.py` 中設定路徑）。

3.  **啟動儀表板**：
    ```bash
    streamlit run app.py
    ```

## 常見問題 (Troubleshooting)

### Q: 執行 python 或 pip 時出現錯誤？
如果您剛安裝 Python，系統可能尚未更新環境變數。請嘗試：
1.  **重啟終端機** (關閉並重新開啟 PowerShell)。
2.  或使用完整路徑執行：
    -   安裝套件：
        ```powershell
        & 'C:\Users\oscar.chang\AppData\Local\Programs\Python\Python312\python.exe' -m pip install -r requirements.txt
        ```
    -   啟動 App：
        ```powershell
        & 'C:\Users\oscar.chang\AppData\Local\Programs\Python\Python312\python.exe' -m streamlit run app.py
        ```

## 檔案結構
- `data_parser.py`：專用於解析特定 BAS CSV 格式（包含 Metadata 與 Pivot 資料）的邏輯。
- `data_pipeline.py`：負責資料清洗與特徵工程運算。
- `app.py`：視覺化儀表板的主程式。
