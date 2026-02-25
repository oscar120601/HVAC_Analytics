# Parser Migration Guide v2.1 -> v2.2

**文件版本:** v1.0  
**日期:** 2026-02-25  
**適用範圍:** HVAC-1 Parser 重構（`src/etl/parser.py` -> `src/etl/parser/`）

---

## 1. 目標

在不破壞既有流程（Container、Cleaner、既有測試）的前提下，完成 Parser v2.2 模組化重構並導入 Siemens Scheduler 格式。

---

## 2. 遷移原則

1. 保留 `src/etl/parser.py` 與 `ReportParser` 相容入口。
2. 新功能以 `src/etl/parser/` 套件實作（Factory + Strategy）。
3. 舊入口僅作為 Facade/Shim，內部委派至 `GenericParser`。
4. 全部驗收通過前，不移除舊 import 路徑。

---

## 3. 分階段步驟

### Phase A: 建立 v2.2 新骨架

1. 新增 `src/etl/parser/` 目錄與 `BaseParser`、`ParserFactory`、`GenericParser`、`SiemensSchedulerReportParser`。
2. 在 `ParserFactory` 提供 `create_parser()` 與 `auto_detect()`（`auto_detect` 非策略類別）。
3. BaseParser 對齊契約：輸出 `timestamp` 為 UTC/ns，metadata 必含 `pipeline_origin_timestamp`。

### Phase B: 相容層接線

1. 保留 `src/etl/parser.py` 的 `ReportParser` 對外 API。
2. `ReportParser.parse_file()` 內部委派 `GenericParser.parse_file()`。
3. 若舊程式碼使用 `site_id` 配置，需轉換為 v2.2 `config` 介面並保持行為一致。

### Phase C: 呼叫端逐步切換

1. 先改新增功能與新模組使用 `ParserFactory`。
2. 逐步調整 `src/container.py` 與新測試使用 v2.2 入口。
3. 舊測試維持可跑，直到新測試與整合測試穩定。

### Phase D: 收斂與退場

1. 確認所有呼叫端不再直接依賴 `ReportParser` 特有行為。
2. 更新文件與任務排程狀態。
3. 規劃下一版移除相容層（非本次 v2.2 範圍）。

---

## 4. 必過檢核清單

- [ ] `tests/test_parser_v21.py` 全數通過（相容驗證）
- [ ] v2.2 新增 parser 測試全數通過
- [ ] Parser -> Cleaner 整合測試通過
- [ ] E101-E105 名稱與語意對齊 SSOT
- [ ] metadata 包含 `pipeline_origin_timestamp`
- [ ] `ParserFactory.auto_detect()` 可正確辨識 Siemens 格式
- [ ] `src/container.py` 在舊入口/新入口下均可初始化

---

## 5. 回滾方案

若 v2.2 上線後發生 Critical 回歸：

1. 將 parser 選擇固定為 `generic`。
2. 維持 `src/etl/parser.py` + `ReportParser` 相容入口執行主流程。
3. 暫停 Siemens 策略入口，待問題修復後再啟用。
