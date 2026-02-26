# 《PRD_Continual_Learning_v1.0.md》審查報告

這份 Continual Learning (持續學習) PRD 引入了先進的 GEM（Gradient Episodic Memory）機制來解決 HVAC 系統漂移問題，設計極具前瞻性。針對軟體架構與實作邏輯，提出以下風險與優化建議：

## 🔴 潛在風險 (Risks)

1. **梯度投影維度配對的數學漏洞 (Ch 4.2, `_apply_gem_constraint`)**
   在 `GEMTrainer` 計算 `dot_product = np.dot(new_gradient, ref_gradient)` 時隱含了一個極大風險：`_extract_gradient(model)` 所取出的梯度，如果是把神經網絡所有層平坦化（flatten）後的一維向量，對於深層模型來說向量極大（動輒十萬以上的維度）。將一個極高維度的全局梯度粗暴地投影到另一個高維向量上，在幾何上通常會因為「維數災難 (Curse of Dimensionality)」而變成幾乎正交 (dot product ≈ 0) 或投影後的梯度失去對原損失面的有效下降指引。正規的做法應該是**分層 (Layer-wise) 處理**並計算梯度投影。

2. **計算 `ref_gradients` 破壞了主模型的計算圖狀態 (Ch 4.2, `_apply_gem_constraint`)**
   在計算記憶體參考梯度時：

   ```python
   optimizer = torch.optim.SGD(model.parameters(), lr=0)
   loss.backward() 
   ```

   這種寫法會在原本主迴圈的 `optimizer.zero_grad()` 到主迴圈 `optimizer.step()` 中間，**覆蓋並污染**了本來就存在 `model.parameters().grad` 上的 `new_gradient`。如果取出梯度後沒有手動將它覆蓋回模型， `optimizer.step()` 最後實際更新的方向是被污染後的殘留梯度。必須使用 `.clone()` 或保留副本的機制管理。

3. **`predict` 無法保留時序特性做災難遺忘監控 (Ch 3.1, `_check_catastrophic_forgetting`)**
   在使用 `old_predictions = old_model.predict(old_samples.X)` 測試時，`old_samples.X` 已經被打散成一筆一筆儲存在 `MemoryBuffer` 裡。但前一份 PRD 中說明了這是一個含有 RNN / 時序展開或是 GNN 的系統，如果在評估不連續、打散的 `MemoryBuffer` 時直接送進有時序狀態 (State) 或依賴鄰接矩陣 (Adjacency Matrix) 的模型，預測出來的值絕對不準，會產生偽「災難性遺忘」。在此必須讓 Memory 儲存完整的序列片段，或是確保推論函式能在打散狀態下正確處理。

4. **K-S 檢定的樣本數敏感度 (Ch 5, `detect_feature_drift`)**
   使用 `ks_2samp` 來做 Feature Drift 偵測時，KS 檢定對於大樣本數據極度敏感。以感測器時間序列資料為例，只要資料點稍微多一些（例如 > 5000），極微小、實際上無害的分布變異都會讓 P-value < 0.05 觸發漂移警報。這會導致不必要的重訓風暴（False Positive Alert Overload）。建議結合 Population Stability Index (PSI) 或是限制比對樣本數來降低敏感度。

## 🟢 優化空間 (Optimization)

1. **記憶體重要抽樣函數化設計 (Ch 6, `sample_batches`)**
   當 `strategy == "importance"` 時，代碼實作為：`scores = np.array([s.importance_score for s in self.buffer])`。每次 `sample` 都要歷遍整個 Buffer 的 list 並轉換成 np.array 並歸一化，對於快速執行的訓練迴圈造成顯著 I/O Overhead。建議將 Importance 的歸一化陣列作為 `EpisodicMemoryBuffer` 的類別狀態（State），並在插入/移除樣本時才觸發增量更新。

2. **設備異動事件 (EquipmentChangeEvent) 處理邏輯遺漏**
   在輸入契約提到了會接收來自 Annotation Manager 的 `equipment_changes`（如新增設備或維修），但後續的 `UpdateOrchestrator` 檢測與處理中完全沒有實際消費這筆資料的流程（例如遇到 Topology Change 應該觸發重新產成 Adjacency Matrix 並初始化 GNN 相關層）。建議在 `should_update` 加回對此 Event 的處理路徑。
