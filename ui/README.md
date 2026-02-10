# HVAC ETL UI 模組

## 概述

本目錄包含 HVAC Analytics 專案的 Streamlit UI 模組，採用**二級選單架構**：
- **一級選單**：處理模式（批次處理 / 最佳化模擬）
- **二級選單**：各模式下的子分頁

## 二級選單架構

```
📁 側邊欄
├── ⚙️ 設定
├── 📌 處理模式（一級選單）
│   ├── [批次處理] 或 [⚡ 最佳化模擬]
│
├── 📂 批次處理選單（二級選單 - 點選批次處理後展開）
│   ├── 📋 解析資料
│   ├── 🧹 清洗資料
│   ├── 📊 統計資訊
│   ├── 📈 時間序列
│   ├── 🔗 關聯矩陣
│   ├── 🎯 資料品質
│   └── 💾 匯出
│
└── ⚡ 最佳化模擬選單（二級選單 - 點選最佳化模擬後展開）
    ├── 🗺️ 特徵映射
    ├── 🎯 即時最佳化
    ├── 📊 特徵重要性
    ├── 📈 歷史追蹤
    └── 🔧 模型訓練
```

## 目錄結構

```
ui/
├── __init__.py           # 模組初始化與匯出
├── sidebar.py            # 側邊欄配置（二級選單邏輯）
├── components.py         # 共用 UI 元件（圖表、表格、度量）
├── batch_page.py         # 批次處理模式頁面
├── optimization_page.py  # 最佳化模擬模式頁面
└── README.md            # 本說明文件
```

## 檔案統計

| 檔案 | 行數 | 職責 |
|------|------|------|
| `sidebar.py` | ~200 行 | 二級選單導航 |
| `components.py` | 531 行 | 共用元件 |
| `batch_page.py` | ~460 行 | 批次處理（7 個子頁面）|
| `optimization_page.py` | ~400 行 | 最佳化模擬（5 個子頁面）|
| `etl_ui.py` | ~60 行 | 主入口 |
| **總計** | **~1,650 行** | - |

## 使用方式

### 主入口

```python
# etl_ui.py
from ui.sidebar import render_sidebar
from ui.batch_page import render_batch_page
from ui.optimization_page import render_optimization_page

# Render sidebar with two-level menu
processing_mode, selected_files, selected_model, current_page = render_sidebar(ML_AVAILABLE)

# Route to appropriate page based on mode and sub-page
if processing_mode == "批次處理":
    render_batch_page(selected_files, current_page)
elif processing_mode == "⚡ 最佳化模擬":
    render_optimization_page(selected_model, current_page)
```

### 新增子分頁

1. 在 `sidebar.py` 的 `BATCH_SUBPAGES` 或 `OPTIMIZATION_SUBPAGES` 列表中添加：

```python
BATCH_SUBPAGES = [
    ("📋 解析資料", "batch_parse"),
    ("🆕 新功能", "batch_new_feature"),  # 新增
    # ...
]
```

2. 在 `batch_page.py` 中實現對應的渲染函數：

```python
def _render_new_feature_tab():
    st.subheader("🆕 新功能")
    # 實現功能
```

3. 在 `render_batch_page()` 函數中添加路由：

```python
elif current_page == "batch_new_feature":
    _render_new_feature_tab()
```

## 狀態管理

使用 Streamlit session_state 管理選單狀態：

```python
# sidebar.py
st.session_state.sidebar_mode    # 當前處理模式
st.session_state.sidebar_page    # 當前子分頁
```

## 開發指南

### 設計原則

1. **單一職責原則**：每個子分頁獨立負責一個功能
2. **狀態分離**：每個模式有自己的 session state 前綴
3. **懶加載**：只有當前子分頁會渲染內容
4. **可重用性**：共用元件放在 `components.py`

### 子分頁模板

```python
def _render_new_tab():
    """渲染新功能子分頁"""
    st.subheader("🆕 新功能標題")
    
    # Check prerequisites
    if 'required_data' not in st.session_state:
        st.info("請先完成前置步驟")
        return
    
    # Main content
    st.write("功能內容...")
```

## 歷史記錄

- **2026-02-10**: 完成模組化重構，將 `etl_ui.py` 從 2,172 行精簡
- **2026-02-10**: 實現二級選單架構，支援展開式子分頁導航
