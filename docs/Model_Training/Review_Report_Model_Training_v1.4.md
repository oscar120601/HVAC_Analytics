# 《PRD_Model_Training_v1.4.md》第二次深度極限審查報告 (2nd Review)

基於 v1.4.1 版本，本報告深入檢視了 GNN 模組、MultiTarget 聯合訓練邏輯與 PyTorch 架構整合設計。在您精準實施首次審查優化後，我們探勘到程式「**聯合訓練 (Joint Training) 設計模式的嚴重缺陷**」，這會導致訓練物理損失時系統崩潰。

---

## 🔴 潛在風險 (Critical Risks)

### 1. **`_train_joint_with_physics_loss` 的架構性謬誤 (Fatal Logic Flaw)**

- **問題現狀**：在 `MultiTargetHybridTrainer._train_joint_with_physics_loss` 實作中，被標榜為「聯合訓練」的階段，其實作寫法如下：

  ```python
  all_targets = [self.system_target] + self.component_targets
  for target in all_targets:
      trainer = self.base_trainer_class(..., physics_loss_fn=self.physics_loss_fn)
      target_result = trainer.train(feature_matrix)
  ```

- **致命風險**：
  這是**「獨立的迴圈逐一訓練」**，並非聯合訓練。當使用 `PhysicsInformedHybridLoss` 時，需要**同時取得**所有模型 (System 與 所有 Components) 在同一個 Batch 的預測張量 (Tensor)，才能計算 `System_Pred - Σ(Component_Preds)`，進而執行 `loss.backward()`。<br/>
  若按現有寫法，在訓練 `system_target` 第一個 Epoch 第一個 Batch 時，底下的 `component_transformers` 模型**甚至還沒啟動訓練**，它們無法也不應該提供預測張量參與該圖計算。這不僅無法算損失，PyTorch 自動微分圖 (Computational Graph) 也會徹底斷裂報錯。
- **架構修正建議**：
  在深度學習裡要達到此要求，請將 `GNNTrainer` 的封裝層級提高。這需要放棄為不同 Target 個別創建 `GNNTrainer` 物件，應採用以下兩種正統方案之一：
  1. **[最佳推薦] 多任務學習架構 (Multi-Task Learning)**：
     - 建構**單一個神經網路模型** (共享 GNN 卷積層提取全域特徵)，在最後全連接層(FC) 改用多輸出頭 (Multi-Head)。讓 `output_dim = 1 + n_components`。
     - 在一個 Forward 之中同時輸出 `[System_Pred, Comp1_Pred, Comp2_Pred...]`。
     - 直接套用 `pred_loss + physical_loss`，只需要維護**一個 Training Loop 和一個 Optimizer**，效能與記憶體開銷降至最低（不用冗餘跑多次 GNN）。
  2. **聯合訓練迴圈 (Joint Optimizer)**：
     - 若硬要保持獨立模型，必須拉出一個宏觀的 Training Loop。將多個獨立模型的 Generator (或 Parameters) 放進同一個 `torch.optim.Adam([*sys_mdl.pars(), *comp1_mdl.pars()...])`，接著在內部 Batch 迴圈中同時對所有模型呼叫 forward 並結合 Loss。
  > 結論：請重構 `MultiTargetHybridTrainer` 或新增 `MultiTaskGNNTrainer`，拋棄迴圈式獨立呼叫 `trainer.train(...)` 想實現聯合優化物理損失的幻想。

### 2. **傳統樹模型與 Tensor Loss 介面衝突**

- **問題現狀**：PRD 文件與配置註解提到「`base_trainer_class` ... 此處以 GNN 為例，但也可用於其他梯度優化模型」。
- **潛在風險**：`PhysicsInformedHybridLoss` 全為 PyTorch Tensor 與 `nn.Module` 計算。傳統模型如 XGBoost / LightGBM 根本無法接收 PyTorch Loss Module，若隨意傳入，在呼叫執行時會發生型別錯誤。XGBoost 只有支援自己專屬定義的一階梯度(Gradient)與二階導數(Hessian)的 Custom Objective 函數，且難以將多個獨立 XGBoost 綁在一起進行梯度的聯合物理約束優化。
- **修正建議**：必須在文件或程式碼防呆中徹底講明：**物理聯合訓練 (Joint Training with Physics Loss) 僅能應用於 PyTorch 基底之模型 (即 GNN)**。如果樹模型要保持物理一致性，只能用後處理 (Post-processing) 縮放，或依賴 Phase 7 作驗證。

---

## 🟢 優化空間 (Optimization & Robustness)

### 1. **GNN 佈署階段 (Inference) 失憶引發的 `AttributeError`**

- **現狀**：在 `GNNTrainer.predict()` 裡有此段防護修正 `if adjacency_matrix is None: adjacency_matrix = self.adjacency_matrix` 讓推論支援未給定矩陣。
- **優化建議**：一旦模型執行 `trainer.save_model("model.pt")` 後，另起一個全新執行緒進行載入推論。新載入的模型實例是**沒有** `self.adjacency_matrix` 屬性的。
  必須在 `save_model` 裡加入拓樸保存，並在 `load_model` 中恢復：

  ```python
  def save_model(self, path: Path):
      torch.save({
          'model_state_dict': self.model.state_dict(),
          'config': self.config.dict(),
          'training_history': self.training_history,
          'feature_importance': getattr(self, 'feature_importance', None),
          'adjacency_matrix': getattr(self, 'adjacency_matrix', None) # 🆕 必須實體保存
      }, path)
  
  def load_model(self, path: Path):
      checkpoint = torch.load(path, map_location=self.device)
      # ...
      self.adjacency_matrix = checkpoint.get('adjacency_matrix', None) # 🆕 必須復原
  ```

### 2. **Captum 特徵重要性的 Baseline 設定 (Integrated Gradients 準確度)**

- **現狀**：在使用 `IntegratedGradients` 計算特徵重要性時：`attributions = ig.attribute(batch.x, target=..., n_steps=50)`。
- **優化建議**：Integrated Gradients (IG) 若不提供 `baselines` 參數，預設是用「全 0」進行參考比較。若特徵做過正規化（例如標準化為均值 0，這時全 0 代表中位數，還算合理），或者沒有做，都會導致積分基準點不適當，特徵重要性分數不可靠。
  **建議**：將驗證資料集特徵每一行的平均值 (或訓練集) 傳入作為 `baselines=train_mean_tensor`，使特徵貢獻結果具有真正的物理及數據意義。

---

## 結語

在這份架構升級中，您針對 3D Tensor 效能瓶頸及共線性問題做了卓越的修正。但本報告挖出的**「迴圈偽聯合訓練 (Sequential Loop posing as Joint Training)」**是架構層面最大的實作盲區。

為因應物理守恆損失，建議引入 **Multi-Task Neural Network** 的典範，讓單一 GNN 模型具備多輸出頭 (Multi-Head)。如果完成修正，這個系統的穩健性將大幅甩開一般的傳統多變數迴歸作法，成為擁有極高技術護城河的 AI 架構！
