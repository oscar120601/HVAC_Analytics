# Sprint 3.1 Feature Engineer v1.4 修正計劃

## 文件資訊
- **文件版本:** v1.0
- **建立日期:** 2026-03-02
- **對應審查報告:** `docs/專案任務排程/Sprint_3_Review_Report.md`
- **對應 PRD:** `docs/feature_engineering/PRD_FEATURE_ENGINEER_V1.4.md`
- **預估工時:** 2-3 天
- **優先級:** 🔴 Critical (需在 Sprint 3.2 Model Training 啟動前完成)

---

## 一、問題總覽

根據審查報告，Sprint 3.1 完成之 `Feature Engineer v1.4` 存在以下類別的問題：

| 類別 | 數量 | 嚴重程度 |
|:---|:---:|:---:|
| 潛在性風險與系統穩定度 | 3 項 | Critical |
| 效能優化空間 | 2 項 | Critical/Medium |
| PRD 對齊度與邏輯偏移 | 3 項 | High/Medium |

---

## 二、詳細修正項目

### 🔴 Critical Priority

#### 1. NaN 與 Null 的序列化漏洞修復

**問題描述:**
在 `_collect_equipment_features` 函式中，僅使用 `is not None` 檢查無法捕捉 `float('nan')`，可能導致 GNN 訓練時 Loss 爆炸。

**目前程式碼 (Line 935):**
```python
col_stats = [s if s is not None else 0.0 for s in col_stats]
```

**修正方案:**
```python
import math
col_stats = [0.0 if s is None or (isinstance(s, float) and math.isnan(s)) else s for s in col_stats]
```

**影響範圍:**
- 檔案: `src/etl/feature_engineer.py`
- 函式: `_collect_equipment_features`
- 行號: 第 927-935 行

**驗收標準:**
- [ ] 全 Null 陣列的統計計算回傳 NaN 時被正確攔截
- [ ] 單元測試覆蓋全 Null 欄位情況

---

#### 2. ST-GNN 3D Tensor 生成效能重構

**問題描述:**
`_generate_3d_tensor` 使用雙層 Python 迴圈逐元素存取 `df[col][t]`，時間複雜度 O(N*T)，大資料集時會崩潰。

**目前程式碼 (Line 1007-1018):**
```python
for t in range(0, n_timesteps, stride):
    tensor_idx = t // stride
    if tensor_idx >= tensor.shape[0]:
        break
    
    for feat_info in time_series_features:
        eq_idx = feat_info['equipment_idx']
        col = feat_info['column']
        if col in df.columns:
            value = df[col][t]  # O(T * N_cols) 代價極大
            tensor[tensor_idx, eq_idx, -1] = value if value is not None else 0.0
```

**修正方案:**
採用 PRD 第 1618-1744 行建議的向量化實作：
```python
def _generate_3d_tensor(
    self,
    df: pl.DataFrame,
    equipment_to_idx: Dict[str, int],
    equipment_features: np.ndarray,
    stride: int = 1,
    dtype: np.dtype = np.float32
) -> Tuple[np.ndarray, List[str]]:
    """
    生成 3D Tensor (T, N, F) 供 ST-GNN 使用 - 向量化重構版
    """
    # 套用 stride 降採樣
    if stride > 1:
        df = df[::stride]
    
    n_timesteps = len(df)
    n_nodes = len(equipment_to_idx)
    
    # 收集時間序列特徵欄位（依設備順序）
    all_feature_cols_ordered = []
    equipment_feature_counts = []
    
    for eq_id in sorted(equipment_to_idx.keys()):
        eq_cols = [
            col for col in df.columns
            if col not in ['timestamp', 'quality_flags']
            and self.annotation_manager.get_column_annotation(col)
            and getattr(self.annotation_manager.get_column_annotation(col), 'equipment_id', None) == eq_id
        ]
        all_feature_cols_ordered.extend(eq_cols)
        equipment_feature_counts.append(len(eq_cols))
    
    if not all_feature_cols_ordered:
        return np.zeros((n_timesteps, n_nodes, 1), dtype=dtype), ['unknown'] * n_nodes
    
    max_features = max(equipment_feature_counts) if equipment_feature_counts else 0
    
    # 記憶體預檢查
    element_size = np.dtype(dtype).itemsize
    estimated_memory_gb = (n_timesteps * n_nodes * (max_features + 1) * element_size) / (1024**3)
    
    if estimated_memory_gb > 4.0:
        import warnings
        warnings.warn(
            f"3D Tensor 預估記憶體占用: {estimated_memory_gb:.2f} GB. "
            f"建議使用 stride > 1 或分批處理",
            ResourceWarning
        )
    
    # 向量化轉換：一次性轉為 NumPy (T, F_total)
    data_matrix = df[all_feature_cols_ordered].to_numpy(dtype=dtype)
    
    # 初始化 3D Tensor
    tensor = np.zeros((n_timesteps, n_nodes, max(max_features + 1, equipment_features.shape[1] + 1)), dtype=dtype)
    
    # 填充靜態設備特徵
    for i in range(n_nodes):
        tensor[:, i, :equipment_features.shape[1]] = equipment_features[i]
    
    # 向量化填充時間序列特徵
    feature_idx = 0
    for i, eq_id in enumerate(sorted(equipment_to_idx.keys())):
        n_eq_features = equipment_feature_counts[i]
        if n_eq_features > 0:
            eq_data = data_matrix[:, feature_idx:feature_idx + n_eq_features]
            
            # NaN 檢測與填充
            nan_mask = np.isnan(eq_data).any(axis=1)
            eq_data_safe = np.nan_to_num(eq_data, nan=0.0)
            
            tensor[:, i, :n_eq_features] = eq_data_safe
            tensor[nan_mask, i, -1] = 1.0  # Mask 標記
            
            feature_idx += n_eq_features
        else:
            tensor[:, i, -1] = 1.0
    
    # 生成 node_types
    node_types = []
    for eq_id in sorted(equipment_to_idx.keys()):
        device_role = self.annotation_manager.get_device_role(eq_id)
        node_types.append(device_role if device_role else "unknown")
    
    return tensor, node_types
```

**影響範圍:**
- 檔案: `src/etl/feature_engineer.py`
- 函式: `_generate_3d_tensor` (完全重寫)
- 行號: 第 953-1020 行

**驗收標準:**
- [ ] 100 個設備 × 50 萬時間步的資料在 10 秒內完成
- [ ] 輸出維度正確 (T, N, F)
- [ ] 回傳 Tuple[np.ndarray, List[str]] 符合 PRD 約定

---

#### 3. Group Policy 解耦實作

**問題描述:**
`generate_topology_aggregation_features` 直接使用 `topology_manager.get_all_equipment()` 遞迴查找，未使用 `resolved_policies` 進行解耦。

**修正方案:**
參考 PRD 第 733-836 行實作 `_generate_topology_from_resolved_policies`，並修改主函式優先使用 resolved_policies：

```python
def generate_topology_aggregation_features(
    self,
    df: pl.DataFrame
) -> Tuple[pl.DataFrame, List[Dict]]:
    """
    生成拓樸聚合特徵 (L2 Features) - Group Policy 解耦版
    """
    config = self.config.topology_aggregation
    if not config or not config.enabled:
        return df, []
    
    # 🆕 優先使用 resolved_policies（若已執行過 _resolve_group_policies_v14）
    if hasattr(self, 'resolved_policies') and self.resolved_policies:
        return self._generate_topology_from_resolved_policies(df, config)
    
    # 原有邏輯作為 fallback
    # ... (保留既有實作)
```

**新增函式:** `_generate_topology_from_resolved_policies`

**影響範圍:**
- 檔案: `src/etl/feature_engineer.py`
- 函式: `generate_topology_aggregation_features` (修改邏輯順序)
- 新增: `_generate_topology_from_resolved_policies` (PRD 第 733-836 行)

**驗收標準:**
- [ ] 當 `resolved_policies` 存在時優先使用
- [ ] 拓樸特徵命名格式符合 `{eq_id}_upstream_{phys_type}_{agg}`
- [ ] 最小有效來源數量檢查正確運作

---

### 🟡 Medium Priority

#### 4. 記憶體降級型別限縮

**問題描述:**
`_optimize_memory_dtype` 使用 `cs.numeric()` 包含整數型別，造成精度流失。

**目前程式碼 (Line 289):**
```python
numeric_cols = df.select(cs.numeric()).columns
```

**修正方案:**
```python
def _optimize_memory_dtype(self, df: pl.DataFrame) -> pl.DataFrame:
    """
    記憶體優化：僅針對 Float 類型進行降級
    """
    # 只選取 Float 類型（排除整數、布林等離散數值）
    float_cols = df.select(cs.float()).columns
    exclude_cols = ['timestamp', 'quality_flags']
    cols_to_optimize = [c for c in float_cols if c not in exclude_cols]
    
    if not cols_to_optimize:
        return df
    
    cast_exprs = [pl.col(c).cast(pl.Float32) for c in cols_to_optimize]
    df_optimized = df.with_columns(cast_exprs)
    
    # 記錄優化資訊
    original_size = df.estimated_size()
    optimized_size = df_optimized.estimated_size()
    saved_mb = (original_size - optimized_size) / (1024 * 1024)
    
    if saved_mb > 10:
        self.logger.info(
            f"記憶體優化: Float 欄位轉型為 Float32，"
            f"預估節省 {saved_mb:.1f} MB"
        )
    
    return df_optimized
```

**影響範圍:**
- 檔案: `src/etl/feature_engineer.py`
- 函式: `_optimize_memory_dtype`
- 行號: 第 285-306 行

**驗收標準:**
- [ ] 整數型態欄位（如狀態碼）保持原有型別
- [ ] Float64 欄位正確降級為 Float32

---

#### 5. 設備靜態特徵提取效能優化

**問題描述:**
`_collect_equipment_features` 逐欄位呼叫統計函數，未使用批次處理。

**修正方案:**
```python
def _collect_equipment_features(
    self,
    df: pl.DataFrame,
    equipment_to_idx: Dict[str, int]
) -> np.ndarray:
    """
    收集每個設備的特徵 - 批次處理優化版
    """
    import math
    
    n_nodes = len(equipment_to_idx)
    equipment_feature_dict = {eq_id: [] for eq_id in equipment_to_idx.keys()}
    
    # 收集每個設備的欄位
    equipment_columns = {eq_id: [] for eq_id in equipment_to_idx.keys()}
    
    for col in df.columns:
        if col in ['timestamp', 'quality_flags']:
            continue
        
        anno = self.annotation_manager.get_column_annotation(col)
        if not anno:
            continue
        
        eq_id = getattr(anno, 'equipment_id', None)
        if not eq_id or eq_id not in equipment_columns:
            continue
        
        equipment_columns[eq_id].append(col)
    
    # 批次計算統計值（每個設備一次 select）
    for eq_id, cols in equipment_columns.items():
        if not cols:
            continue
        
        # 使用 Polars 批次計算
        stats_df = df.select([
            pl.col(c).mean().alias(f"{c}_mean") for c in cols
        ] + [
            pl.col(c).std().alias(f"{c}_std") for c in cols
        ] + [
            pl.col(c).min().alias(f"{c}_min") for c in cols
        ] + [
            pl.col(c).max().alias(f"{c}_max") for c in cols
        ])
        
        # 提取統計值（含 NaN 檢查）
        for c in cols:
            col_stats = [
                stats_df[f"{c}_mean"][0],
                stats_df[f"{c}_std"][0],
                stats_df[f"{c}_min"][0],
                stats_df[f"{c}_max"][0]
            ]
            # NaN 與 Null 檢查
            col_stats = [
                0.0 if s is None or (isinstance(s, float) and math.isnan(s)) else float(s)
                for s in col_stats
            ]
            equipment_feature_dict[eq_id].extend(col_stats)
    
    # 組成矩陣
    max_features = max(len(feats) for feats in equipment_feature_dict.values()) if equipment_feature_dict else 0
    feature_matrix = np.zeros((n_nodes, max_features), dtype=np.float32)
    
    for eq_id, idx in equipment_to_idx.items():
        feats = equipment_feature_dict.get(eq_id, [])
        while len(feats) < max_features:
            feats.append(0.0)
        feature_matrix[idx, :len(feats)] = feats[:max_features]
    
    return feature_matrix
```

**影響範圍:**
- 檔案: `src/etl/feature_engineer.py`
- 函式: `_collect_equipment_features` (重構)
- 行號: 第 897-951 行

**驗收標準:**
- [ ] 使用單一 `df.select()` 批次計算每個設備的統計值
- [ ] 正確處理 NaN 與 None

---

#### 6. 拓樸特徵前向填充邏輯釐清

**問題描述:**
PRD 總覽提到 `forward -> 0.0`，但實際程式碼使用 `.fill_null(strategy="forward")`。

**決議:**
根據 PRD 第 827-834 行，拓樸特徵使用前向填充是合理的（利用過去觀測值填補當下缺漏無資料洩漏疑慮）。

**行動:**
在程式碼中加入註解說明，並更新 PRD 總覽以明確區分適用範圍：

```python
# 拓樸特徵時間序列連續性填充
# 注意：forward fill 對拓樸聚合特徵無 Look-ahead Bias 疑慮
# 因為這是利用「過去已存在的觀測值」填補「當下缺漏」，不涉及未來資料
df = df.with_columns(
    cs.starts_with("_upstream_")
    .fill_null(strategy="forward")
    .fill_null(0.0)
)
```

---

#### 7. GNN 回傳型別統一

**問題描述:**
`export_gnn_data` 回傳 `Dict[str, Any]`，但 PRD 要求 `export_gnn_data` 調用的內部函數回傳 `Tuple[np.ndarray, List[str]]`。

**修正方案:**
確保以下函數回傳型別統一：
- `_generate_3d_tensor` → 回傳 `Tuple[np.ndarray, List[str]]`
- `_collect_equipment_features` (靜態特徵) → 保持 `np.ndarray`
- `export_gnn_data` 整體 → 保持 `Dict[str, Any]` (這是對外介面)

已在項目 2 的修正方案中統一回傳型別。

---

## 三、實作順序建議

| 順序 | 項目 | 工時 | 相依性 |
|:---:|:---|:---:|:---|
| 1 | NaN 與 Null 的序列化漏洞修復 | 0.5 天 | 無 |
| 2 | ST-GNN 3D Tensor 生成效能重構 | 1 天 | 項目 1 |
| 3 | Group Policy 解耦實作 | 0.5 天 | 無 |
| 4 | 記憶體降級型別限縮 | 0.3 天 | 無 |
| 5 | 設備靜態特徵提取效能優化 | 0.5 天 | 項目 1 |
| 6 | 拓樸特徵前向填充邏輯釐清 | 0.2 天 | 無 |
| 7 | GNN 回傳型別統一 | 0.2 天 | 項目 2 |

**總計: 2.5-3 天**

---

## 四、測試計劃

### 單元測試新增/修改

```python
# tests/test_feature_engineer_v14.py 新增以下測試案例

class TestFeatureEngineerCorrections:
    """Sprint 3.1 修正項目測試"""
    
    def test_nan_handling_in_equipment_features(self):
        """測試全 Null 陣列的 NaN 處理"""
        # 建立全 Null 欄位
        pass
    
    def test_3d_tensor_performance(self):
        """測試 3D Tensor 生成效能"""
        # 使用 100 設備 × 10000 時間步的資料
        # 驗證執行時間 < 5 秒
        pass
    
    def test_resolved_policies_priority(self):
        """測試 resolved_policies 優先使用"""
        pass
    
    def test_memory_dtype_optimization_excludes_integers(self):
        """測試整數欄位不被降級"""
        pass
    
    def test_3d_tensor_return_type(self):
        """測試 3D Tensor 回傳型別為 Tuple[np.ndarray, List[str]]"""
        pass
```

---

## 五、風險與因應措施

| 風險 | 影響 | 因應措施 |
|:---|:---:|:---|
| 3D Tensor 重構導致維度錯誤 | High | 增加維度驗證測試，與舊版輸出比對 |
| Group Policy 解耦破壞既有邏輯 | Medium | 保留既有邏輯作為 fallback |
| NaN 檢查影響效能 | Low | 使用向量化 NumPy 操作 |

---

## 六、驗收檢查清單

- [ ] NaN 檢查正確運作（`math.isnan()`）
- [ ] 3D Tensor 效能達標（向量化實作）
- [ ] Group Policy 解耦實作完成
- [ ] 記憶體降級限縮至 Float 類型
- [ ] 設備特徵批次計算實作
- [ ] 回傳型別統一為 Tuple[np.ndarray, List[str]]
- [ ] 所有既有測試通過（回歸測試）
- [ ] 新增測試覆蓋所有修正項目

---

## 附錄：對照表

| 審查報告問題 | 本計劃項目 | PRD 對應章節 |
|:---|:---:|:---|
| 1.1 NaN 與 Null 序列化漏洞 | 項目 1 | 第 1.1 節 `🆕 全 Null 陣列檢查` |
| 1.2 記憶體降級過度轉型 | 項目 4 | 第 448-494 節 `_optimize_memory_dtype` |
| 1.3 safe_float 輔助函式 | 已存在 | 第 1977-1982 節 `_safe_float` |
| 2.1 ST-GNN 3D Tensor 效能崩壞 | 項目 2 | 第 1618-1744 節 `_generate_temporal_feature_tensor` |
| 2.2 設備靜態特徵提取效能 | 項目 5 | 第 1481-1578 節 `_generate_static_feature_matrix` |
| 3.1 Group Policy 解耦 | 項目 3 | 第 733-836 節 `_generate_topology_from_resolved_policies` |
| 3.2 前向填充邏輯矛盾 | 項目 6 | 第 827-834 節（註解說明） |
| 3.3 GNN 回傳型別約定 | 項目 7 | 第 1388, 1626 節 Tuple 回傳 |
