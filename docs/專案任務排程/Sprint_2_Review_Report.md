# Sprint 2: 2.1 Parser v2.1 任務檢測與審查報告

**報告日期:** 2026-02-23  
**審查對象:** Core ETL 模組 - Parser v2.1  
**對應任務:** P-001 ~ P-008

## 1. 檢測摘要與修正結果

在對 Parser v2.1 進行深度原始碼檢測（Code Review）與單元測試（Unit Test）運行後，確認大部分任務皆已完善實作，但在此過程中發現並**即時修正了 3 項關鍵缺陷**，目前所有 16 個 `test_parser_v21.py` 測試案例皆以 `PASSED` 狀態通過。

### 發現與已修復的問題 (Bug Fixes)
1. **標頭正規化不符合 PRD 規範 (未支援中文且缺少 snake_case 完整轉換)**
   - **原本缺失**：原本的 `_normalize_header` 只移除了空白與 `<>` 前綴，且使用 `[^a-zA-Z0-9]` 正則表達式，會導致「所有中文字元」被替換為底線，同時也沒有針對 `CamelCase` 到 `snake_case` 提供邏輯轉換。
   - **修正結果**：已引入 PRD 裡面所規範的 6 步驟轉換邏輯 (`([a-z0-9])([A-Z])` → `\1_\2`)，並將正則表達式改為 `[^\w]` 來保留中文字元，確保在支援智慧中文標頭的情況下，不破壞原先欄位語意。
2. **時區轉換預設值問題導致測試誤報**
   - **原本缺失**：`TestP21_003_Timezone_Conversion` 使用了 `site_id="test"` 來建立 Parser。但在 `site_templates.yaml` 中，`test` 設定的預設時區（assumed_timezone）為 `UTC`，導致測試程式想驗證 `Asia/Taipei` 到 `UTC` 的推算時判定出現 `8 != 0` 的錯誤（因為 Parser 認為它原本就是 UTC 而跳過了扣除 8 小時的階段）。
   - **修正結果**：在該項測試中，主動注入覆寫 `self.parser.config["assumed_timezone"] = "Asia/Taipei"`，使其能正確通過 UTC+8 時區轉換驗證。
3. **整合測試針對大小寫抓取的問題**
   - **原本缺失**：測試案例 `df["Chiller_Current"]` 忘記顧及透過 `Parser` 後，這欄位已經因為字典轉換被標準化為 `chiller_current`，引發 Polars 拋出 `ColumnNotFoundError`。
   - **修正結果**：修正測試檔案中調借的值，並全面將 `Value` 等測試假欄位調降為 `value` 以吻合 snake_case。

## 2. 程式碼架構與契約檢視 (SSOT Alignment)

檢查報告證實 `src/etl/parser.py` 高度遵循了**Interface Contract v1.1**。

* **E101-E105 錯誤保護良好**：
  * `_detect_encoding()` 會主動讀取 binary file bytes 藉由標頭 `BOM` (b"\xef\xbb\xbf") 捕捉 UTF-8-sig、UTF-16，也能自動 fallback 給 Big5 `cp950`，對應 E101。
  * `_standardize_timezone()` 強制輸出了 `Datetime(ns, UTC)`，不符合精度或無法轉換會直接拋出 E102。
  * `_validate_output_contract()` 正確銜接了 `VALID_QUALITY_FLAGS` 等 SSOT 設定，防止未來字典檔修改而產生不同步（Zero Gap 銜接）。 

## 3. 潛在風險與優化建議 (Potential Risks)

根據當前系統實作的 Polars 版本與資料處理行為，提出下方建議供未來參考：

1. **記憶體與過大檔案的 `infer_schema_length`**
   - `pl.read_csv` 的 `infer_schema_length` 目前設定為 `1000`。若資料中混雜空值、前 1000 筆為純數字而第 2000 筆突然出現帶有字元的髒資料時（例如第 2000 行才出現 `"Error"` 或 `"N/A"`），將可能發生 Polars DataFrame 解析失敗的風險。
   - **建議**：目前在 `read_csv` 中加上了 `ignore_errors=True` 來妥協，但若未來需要精準抓錯，可考量指定所有非日期欄位的 schema 預設為 `pl.Utf8`，最後在 `_clean_and_cast()` 時再統一向下型別轉換為 `Float64`。
2. **多個時區混合的情境不在支援範圍**
   - 目前的時區檢查以檔案欄位中 `timestamp` 抓取的數值或透過 `.yaml` 配置中的 `assumed_timezone` 給予全域假設。如果遇到多地案場設備將 Timestamp 放進「同一支 CSV」，目前實作會將整支檔案當作同一種預設時區處理。
   - **建議**：這屬於已知的功能邊界，只要案場報表均依據各單一案場收集即無礙。
3. **Regex 對於中文字集的捕捉寬容度**
   - 目前的 Regex 以 `[^\w]` 清洗「非法標頭字元」，這會直接保留所有的特殊中文字元，但包含「數字開頭」依然會加上 `col_`。(如：`1號冰水主機` → `col_1號冰水主機` )。
   - 表現符合預期，但要告知後方 Cleaner 開發人員與 Feature Engineer 注意這些中文標題若通過了 Parser，在取用 Feature Annotation mapping 時必須小心大小寫及 `col_` 前綴。

## 4. 模組交付物狀態

經過嚴格修正與覆測後，所有檔案已達 `READY FOR SPRINT 2 NEXT STEP` 標準：

* ✅ `src/etl/parser.py`：通過 16 項邏輯安全及格式驗證與契約化要求。
* ✅ `src/exceptions.py`：配合合約補齊所需拋出物件。
* ✅ `config/site_templates.yaml`：正常運作並支撐物件繼承（inherit）架構。
* ✅ `tests/test_parser_v21.py`：單元測試從原本 8 個案例追加延伸條件驗證，共 16 項全數通過，無誤爆情況。

## 5. 結論

**Parser v2.1** 開發任務品質極高，防禦性極強，且所有契約驗證（Interface Contract）完全遵循。前期遇到的 `CamelCase` 標題轉換破壞等瑕疵也已全面解決。

目前可以安穩地將成果對接到接下來負責設備驗證的 **Cleaner v2.2** 任務。
