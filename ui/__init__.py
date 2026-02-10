"""
HVAC ETL UI 模組包

包含所有 Streamlit UI 頁面和元件
採用二級選單架構：處理模式 → 子分頁
"""

from .sidebar import render_sidebar, get_page_title
from .batch_page import render_batch_page
from .optimization_page import render_optimization_page
from .components import (
    get_analysis_numeric_cols,
    show_file_list,
    show_data_metrics,
    show_correlation_heatmap,
    show_time_series,
    show_quality_dashboard,
)

__all__ = [
    'render_sidebar',
    'get_page_title',
    'render_batch_page',
    'render_optimization_page',
    'get_analysis_numeric_cols',
    'show_file_list',
    'show_data_metrics',
    'show_correlation_heatmap',
    'show_time_series',
    'show_quality_dashboard',
]
