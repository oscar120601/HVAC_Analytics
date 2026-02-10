# HVAC ETL UI 模組

## 概述

本目錄包含 HVAC Analytics 專案的 Streamlit UI 模組，採用模組化架構將原本單一的 `etl_ui.py` 拆分為多個職責分明的檔案。

## 目錄結構

```
ui/
├── __init__.py           # 模組初始化與匯出
├── sidebar.py            # 側邊欄配置（處理模式選擇、檔案選擇）
├── components.py         # 共用 UI 元件（圖表、表格、度量）
├── batch_page.py         # 批次處理模式頁面
├── optimization_page.py  # 最佳化模擬模式頁面
└── README.md            # 本說明文件
```

## 檔案統計

| 檔案 | 行數 | 職責 |
|------|------|------|
| `sidebar.py` | 122 行 | 側邊欄配置 |
| `components.py` | 531 行 | 共用元件 |
| `batch_page.py` | 465 行 | 批次處理模式 |
| `optimization_page.py` | 397 行 | 最佳化模擬模式 |
| `etl_ui.py` | 59 行 | 主入口 |
| **總計** | **~1,574 行** | - |

## 重構前後對比

| 項目 | 重構前 | 重構後 |
|------|--------|--------|
| 主檔案行數 | 2,172 行 | 59 行 |
| 總行數 | 2,172 行 | ~1,574 行 |
| 檔案數量 | 1 個 | 6 個 |
| 職責分離 | 否 | 是 |
| 可測試性 | 低 | 高 |
| 維護難度 | 高 | 低 |

## 使用方式

### 主入口

```python
# etl_ui.py
from ui.sidebar import render_sidebar
from ui.batch_page import render_batch_page
from ui.optimization_page import render_optimization_page

# Render sidebar
processing_mode, selected_files, selected_model = render_sidebar(ML_AVAILABLE)

# Route to appropriate page
if processing_mode == "批次處理（整個資料夾）":
    render_batch_page(selected_files)
elif processing_mode == "⚡ 最佳化模擬":
    render_optimization_page(selected_model)
```

### 使用共用元件

```python
from ui.components import (
    show_data_metrics,
    show_correlation_heatmap,
    show_time_series,
    get_analysis_numeric_cols,
)

# 顯示資料度量
show_data_metrics(df)

# 顯示相關性熱圖
show_correlation_heatmap(df)

# 顯示時間序列
show_time_series(df)
```

## 開發指南

### 新增頁面

1. 在 `ui/` 目錄建立新檔案，例如 `new_feature_page.py`
2. 實現 `render_new_feature_page()` 函數
3. 在 `__init__.py` 中匯出
4. 在 `etl_ui.py` 中加入路由

### 新增共用元件

1. 在 `components.py` 中新增函數
2. 遵循命名規範：`show_*` 或 `get_*`
3. 新增型別提示和 docstring
4. 在 `__init__.py` 中匯出

## 設計原則

1. **單一職責原則**：每個模組只負責一個功能
2. **高內聚低耦合**：相關功能放在一起，模組間依賴最小化
3. **可重用性**：共用元件設計為通用型
4. **可測試性**：每個函數可獨立測試

## 歷史記錄

- **2026-02-10**: 完成模組化重構，將 `etl_ui.py` 從 2,172 行精簡至 59 行
