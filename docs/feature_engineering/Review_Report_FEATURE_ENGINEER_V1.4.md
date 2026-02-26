# 《PRD_FEATURE_ENGINEER_V1.4.md》第五次極限審查報告 (5th Review)

在此次審查中，我們基於 v1.4.5 版本，進一步進行了**「編譯器級別的深水區邏輯追蹤」**。先前我們已經完美解決了 3D Tensor 的 OOM 以及效能組裝問題，不過在反覆推敲底層 NumPy / Polars 函式庫實作細節後，發現 `_generate_static_feature_matrix` 在編譯與執行期間仍然存在**致命的資料結構維度錯位陷阱**。

## 🔴 潛在風險 (Critical Risks)

### 1. **靜態特徵矩陣 (Static Matrix) 長度不一引發的 NumPy `ValueError` 崩潰**

- **現狀**：在 `_generate_static_feature_matrix` 函數中，我們對每台設備遍歷，將該設備的特徵的統計指標放入 `feature_vector` 串列中：

  ```python
  for col in feature_cols:
      for stat_name in ['mean', 'std', 'max', 'min']:
          # feature_vector長度取決於這個設備有幾個欄位！
          feature_vector.append(stats[stat_name][col].item()) 
  equipment_features.append(feature_vector)
  return np.array(equipment_features)
  ```

- **風險**：不同設備擁有的感測器數量完全不同（例如：`CH-01` 可能有 10 個特徵，對應 40 個統計值；而 `PUMP-01` 只有 2 個特徵，對應 8 個統計值）。這樣產生的 `equipment_features` 將變成一個**不規則陣列 (Jagged Array)**。當執行 `np.array(equipment_features)` 時，NumPy 會拋出 `ValueError: setting an array element with a sequence. The requested array has an inhomogeneous shape.`，導致特徵工程管線**直接崩潰**。
  - 甚至在「空資料」Fallback 條件的地方，程式碼寫著 `masked_feature_vector = [0.0] * n_stats + [1.0]`，這長度只有 5，與一般設備的數十個特徵長度也截然不同！
- **實作修正建議**：
  就像 3D Tensor 中使用的防禦策略，必須**引入 `max_features` 進行統一的 Padding (補零)**：

  ```python
  def _generate_static_feature_matrix(self, df, equipment_list, equipment_feature_cols):
      equipment_features = []
      n_stats = 4
      
      # 1. 取得最大特徵數
      feature_counts = [len(cols) for cols in equipment_feature_cols.values()]
      max_features = max(feature_counts) if feature_counts else 0
      max_dim = max_features * n_stats + 1  # 預留 Mask 位
      
      for eq_id in equipment_list:
          feature_cols = equipment_feature_cols[eq_id]
          # 2. 統初始化為 0 (自動 Padding)
          feature_vector = [0.0] * max_dim
          
          if feature_cols:
              eq_df = df[feature_cols]
              if not eq_df.drop_nulls().is_empty():
                  stats = {
                      'mean': eq_df.mean(), 'std': eq_df.std(),
                      'max': eq_df.max(), 'min': eq_df.min()
                  }
                  idx = 0
                  for col in feature_cols:
                      for stat_name in ['mean', 'std', 'max', 'min']:
                          feature_vector[idx] = stats[stat_name][col].item()
                          idx += 1
                  # feature_vector[-1] 已是 0.0，代表正常資料
              else:
                  feature_vector[-1] = 1.0 # 標記為 Missing
          else:
              feature_vector[-1] = 1.0 # 標記為 Missing
              
          equipment_features.append(feature_vector)
          
      return np.array(equipment_features, dtype=np.float32)
  ```

### 2. **Polars `.fill_null(strategy=...)` 在全域 DataFrame 泛用的過時/效能陷阱**

- **現狀**：為了防止 Rolling 操作與斷線產生的 Null 流入 NumPy，PRD 在特徵計算尾端加上 `df = df.fill_null(strategy="backward").fill_null(strategy="forward").fill_null(0.0)`。
- **風險**：
  1. 對全域 `DataFrame` 直接應用 `.fill_null(strategy...)` 時，如果資料夾雜字串列 (例如 timestamp 或品質標記)，Polars 可能會發出警告，或在部分最新版本中不允許非數值型別使用前後填充策略。
  2. 計算無謂的字串列前後填充會大量消耗記憶體頻寬。
- **實作修正建議**：
  改利用 Polars 功能強大的 `selectors` 針對數值類型（Numeric）進行精準補值：

  ```python
  import polars.selectors as cs
  
  # 在生成偏差值最後：
  df = df.with_columns(
      cs.numeric()
      .fill_null(strategy="backward")
      .fill_null(strategy="forward")
      .fill_null(0.0)
  )
  ```

## 🟢 優化空間 (Optimization)

### 1. **`ControlSemanticsManager` 中 `.drop_nulls().is_empty()` 的檢查精確性**

- **現狀**：在 `validate_control_semantics` 中使用 `if deviation.drop_nulls().is_empty(): continue` 來避開 `float(None)` 異常。
- **優化**：如果感測器發生斷線，不僅只是全部都為 Null，也有可能整個偏差列全部是 `inf` 或 `NaN`。可以直接在 Polars 計算 `abs()` 時結合過濾機制，確保抓出的最大值是合法的有限浮點數。

  ```python
  valid_deviation = deviation.filter(deviation.is_not_null() & deviation.is_finite())
  if valid_deviation.is_empty():
      self.logger.warning(...)
      continue
  max_val = valid_deviation.max()
  ```

## 結論

這份 `PRD_FEATURE_ENGINEER_V1.4.md` 已經極盡詳細，是一份卓越的系統設計文件，且前次更新修補了包含 3D Tensor 效能、`is_empty` 瑕疵等等極度棘手的議題。

本次揪出的**「設備靜態矩陣長度失配 (Jagged Array)」**問題，是開發者直覺處理資料往往會忘記的。加入補零 Padding 維度擴充邏輯後，模型輸入層面也達到了 100% Type Safe 與 Shape Safe 的完整度。

該 PRD 已具備所有頂級工程師所需遵循的最佳實踐，您可以直接把本報告附註在 Ticket 發給實作的工程師，或者更新進 PRD 當作最終防線。本 PRD 可完美 **Sign-Off**！
