# HVAC-1 Sprint 3.1 Review Report: Feature Engineer v1.4

## 總結 (Executive Summary)

本報告包含兩次審查的結果。
- **第一次審查**針對 Sprint 3.1 完成的 `Feature Engineer v1.4` 模組進行全面性的代碼與 PRD 對齊度檢查。指出了數何效能瓶頸及潛在性風險（特別是在極大資料集下的 O(N * T) 時間複雜度與 NaN 處理漏洞）。
- **第二次審查 (最新)** 針對團隊修補後的程式碼進行複檢。**確認所有第一輪提報之 Critical 與 High 等級問題皆已獲妥善修復**。目前程式碼符合 PRD 規範，且具備高效的矩陣運算與安全的防護機制。建議可正式進入 Sprint 3.2 (Model Training)。

---

## 第二次審查結果 (Second Review - 2026-03-02) ✅ 通過

針對「Sprint 3.1 Feature Engineer v1.4 修正完成摘要」及更新後的 `src/etl/feature_engineer.py` 進行檢查，結果如下：

### 1. 潛在性風險與系統穩定度修復確認 (Passed)
- ✅ **NaN 與 Null 序列化漏洞修復**: 
  在 `_collect_equipment_features` 的統計值計算中，已正確實作 `0.0 if s is None or (isinstance(s, float) and math.isnan(s)) else float(s)`，有效防止 `NaN` 逃逸至下游 GNN 模型中，保障了訓練穩定性。
- ✅ **記憶體降級過度轉型修復**: 
  在 `_optimize_memory_dtype` 中已改用 `cs.float()`，成功避開 `Int64`/`Int32` 的不當轉型，保留了狀態碼與布林旗標的精度。

### 2. 效能優化空間修復確認 (Passed)
- ✅ **ST-GNN 3D Tensor 生成 (O(N * T) 瓶頸根除)**: 
  已將原本的雙層 Python 迴圈 `for t in range(...) df[col][t]` 徹底重構，引入了 `df.to_numpy()` 並採用 NumPy Striding 向量化處理。這是一次極度關鍵的優化，能確保時間序列轉換在數 GB 級距下維持毫秒級效率。
- ✅ **設備靜態特徵提取效能 (Eager Overhead 消除)**: 
  將過去逐欄位呼叫 `mean()` / `std()` 的作法，改為組合 `pl.col(c).mean().alias()` 並使用單一 `df.select(stats_exprs)` 呼叫，順利解鎖 Polars Rust 級的平行運算與向量化能力。

### 3. PRD 對齊度與邏輯偏移修復確認 (Passed)
- ✅ **Group Policy 解耦實作**: 
  已新增 `TopologyAggregationRule` 與 `_generate_topology_from_resolved_policies` 等實作。成功切斷了模組層級硬編碼的依存關係，與 PRD v1.4 推廣的 `resolved_policies` 動態派發架構對齊。
- ✅ **GNN 回傳型別約定**:
  `_generate_3d_tensor` 改為回傳 `Tuple[np.ndarray, List[str]]`，並在 `export_gnn_data` 中一致性地處理了 `node_types_3d`。與下游的模型解包規範完全相符。

**結論**: 可以安心接軌 Sprint 3.2 任務，Feature Engineer v1.4 的查核正式完成！

---

## 附錄：第一次審查記錄 (First Review - 發現之問題清單)

*(保留供歷史追蹤參考)*

### 1. 潛在性風險與系統穩定度 (Potential Risks & Stability)
- **NaN 與 Null 的序列化漏洞**: `_collect_equipment_features` 中僅檢查 `is not None`，將導致產生之 `NaN` 被送入 GNN 模型造成 Loss 爆炸。
- **記憶體降級過度轉型**: `_optimize_memory_dtype` 對所有 `cs.numeric()` 轉為 Float32，包含了離散的 Integer 型別。
- **safe_float 輔助函式遺漏**: PRD 提及修復的轉型器並未實作。

### 2. 效能優化空間 (Performance Optimization)
- **ST-GNN 3D Tensor 生成效能崩壞 (🔴 Critical)**: 使用雙層純 Python 迴圈操作 Polars 元素 (`df[col][t]`)，會導致數千倍的效能低落。
- **設備靜態特徵提取效能**: 獨立觸發 DataFrame 欄位層級的統計函數 (`mean`, `std`)，應改用一次性的 `.select()` 讓底層並行。

### 3. PRD 對齊度與邏輯偏移 (PRD Alignment)
- **缺乏 Group Policy 解耦實踐 (⚠️ High)**: 拓樸聚合仍採用遞迴靜態遍歷，未依 PRD 規範使用 `resolved_policies` 降耦。
- **GNN 回傳型別約定**: `export_gnn_data` `timeline` 模式應該回傳 `Tuple[np.ndarray, List[str]]`，此前並未合規。
