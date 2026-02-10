"""
批次處理模式頁面
包含特徵映射配置和批次處理邏輯
"""

import streamlit as st
import polars as pl
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import components
from .components import (
    show_file_list,
    show_data_metrics,
    get_analysis_numeric_cols,
    show_export_buttons,
)

# Try to import feature mapping
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from config.feature_mapping_v2 import FeatureMapping, PREDEFINED_MAPPINGS, STANDARD_CATEGORIES
    FEATURE_MAPPING_AVAILABLE = True
except ImportError:
    FEATURE_MAPPING_AVAILABLE = False
    FeatureMapping = None
    PREDEFINED_MAPPINGS = {}
    STANDARD_CATEGORIES = {}

# Try to import ETL modules
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from etl.parser import ReportParser
    from etl.cleaner import DataCleaner
    ETL_AVAILABLE = True
except ImportError:
    ETL_AVAILABLE = False
    ReportParser = None
    DataCleaner = None


def render_batch_page(selected_files: List[str]):
    """
    渲染批次處理頁面
    
    Args:
        selected_files: 選擇的檔案列表
    """
    st.header("📦 批次處理模式")
    st.info(f"準備處理 {len(selected_files)} 個檔案")
    
    # Show file list
    show_file_list(selected_files)
    
    st.markdown("---")
    
    # Create tabs for batch processing
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📋 解析資料", 
        "🧹 清洗資料", 
        "📊 統計資訊", 
        "📈 時間序列",
        "🔗 關聯矩陣",
        "🎯 資料品質",
        "💾 匯出"
    ])
    
    with tab1:
        _render_parse_tab(selected_files)
    
    with tab2:
        _render_clean_tab()
    
    with tab3:
        _render_stats_tab()
    
    with tab4:
        _render_timeseries_tab()
    
    with tab5:
        _render_correlation_tab()
    
    with tab6:
        _render_quality_tab()
    
    with tab7:
        _render_export_tab()


def _render_parse_tab(selected_files: List[str]):
    """渲染解析資料標籤頁"""
    st.header("原始資料解析")
    
    if not ETL_AVAILABLE:
        st.error("ETL 模組無法載入")
        return
    
    # Parse first file to show preview
    if st.button("📂 解析並合併資料", type="primary"):
        try:
            with st.spinner(f"正在解析 {len(selected_files)} 個檔案..."):
                data_dir = Path("data/CGMH-TY")
                file_paths = [str(data_dir / f) for f in selected_files]
                
                parser = ReportParser()
                
                # Parse each file and merge
                dfs = []
                for i, fp in enumerate(file_paths):
                    df = parser.parse_file(fp)
                    dfs.append(df)
                
                # Merge all dataframes
                if len(dfs) == 1:
                    merged_df = dfs[0]
                else:
                    merged_df = pl.concat(dfs, how='vertical_relaxed')
                
                st.session_state['batch_merged_df'] = merged_df
                st.session_state['batch_file_count'] = len(selected_files)
                
                st.success(f"✅ 成功解析並合併 {len(selected_files)} 個檔案，共 {len(merged_df):,} 筆資料")
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ 批次處理錯誤: {str(e)}")
            st.exception(e)
    
    # Show preview if data exists
    if 'batch_merged_df' in st.session_state:
        merged_df = st.session_state['batch_merged_df']
        
        # Show basic metrics
        st.subheader("合併後資料概覽")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("總列數", f"{len(merged_df):,}")
        with col2:
            st.metric("總欄位數", f"{len(merged_df.columns):,}")
        with col3:
            st.metric("來源檔案數", st.session_state.get('batch_file_count', 0))
        
        # Data preview
        st.subheader("資料預覽（前 50 筆）")
        st.dataframe(
            merged_df.head(50).to_pandas(),
            use_container_width=True,
            height=400
        )
        
        # Column list
        st.subheader("欄位清單")
        col_list = st.columns(4)
        for i, col in enumerate(merged_df.columns):
            with col_list[i % 4]:
                st.text(f"• {col}")


def _render_clean_tab():
    """渲染清洗資料標籤頁"""
    st.header("資料清洗")
    
    if 'batch_merged_df' not in st.session_state:
        st.info("請先在「解析資料」分頁解析檔案")
        return
    
    if not ETL_AVAILABLE:
        st.error("ETL 模組無法載入")
        return
    
    merged_df = st.session_state['batch_merged_df']
    
    # Cleaning options
    st.subheader("清洗選項")
    
    col1, col2 = st.columns(2)
    with col1:
        resample_interval = st.selectbox(
            "重採樣間隔",
            ["5m", "10m", "15m", "30m", "1h"],
            index=0
        )
    with col2:
        detect_frozen = st.checkbox("檢測凍結資料", value=True)
    
    # Physics-based validation options
    st.subheader("物理驗證選項")
    col1, col2, col3 = st.columns(3)
    with col1:
        apply_steady_state = st.checkbox("穩態檢測", value=False,
            help="只保留負載變化小於 5% 的穩態資料")
    with col2:
        apply_heat_balance = st.checkbox("熱平衡驗證", value=False,
            help="驗證 Q = Flow × ΔT 關係")
    with col3:
        apply_affinity = st.checkbox("親和力定律檢查", value=False,
            help="驗證泵浦 Power ∝ Frequency³ 關係")
    
    # Filter options
    filter_invalid = st.checkbox("移除無效資料", value=False,
        help="移除未通過上述驗證的資料列")
    
    if st.button("🧹 開始清洗", type="primary"):
        try:
            with st.spinner("正在清洗資料..."):
                cleaner = DataCleaner(resample_interval=resample_interval)
                df_clean = cleaner.clean_data(
                    merged_df,
                    apply_steady_state=apply_steady_state,
                    apply_heat_balance=apply_heat_balance,
                    apply_affinity_laws=apply_affinity,
                    filter_invalid=filter_invalid
                )
            
            st.success(f"✅ 清洗完成！")
            
            # Show metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("原始列數", f"{len(merged_df):,}")
            with col2:
                st.metric("清洗後列數", f"{len(df_clean):,}")
            with col3:
                retention = len(df_clean) / len(merged_df) * 100 if len(merged_df) > 0 else 0
                st.metric("保留率", f"{retention:.1f}%")
            
            # Validation results
            validation_results = []
            if apply_steady_state and "is_steady_state" in df_clean.columns:
                steady_count = df_clean["is_steady_state"].sum()
                validation_results.append(f"穩態資料: {steady_count} 筆")
            if apply_heat_balance and "heat_balance_invalid" in df_clean.columns:
                invalid_count = df_clean["heat_balance_invalid"].sum()
                validation_results.append(f"熱平衡異常: {invalid_count} 筆")
            if apply_affinity and "affinity_law_invalid" in df_clean.columns:
                invalid_count = df_clean["affinity_law_invalid"].sum()
                validation_results.append(f"親和力定律異常: {invalid_count} 筆")
            
            if validation_results:
                st.info(" | ".join(validation_results))
            
            # Preview
            st.subheader("清洗後資料預覽")
            st.dataframe(
                df_clean.head(100).to_pandas(),
                use_container_width=True,
                height=400
            )
            
            # Frozen data detection
            frozen_cols = [col for col in df_clean.columns if '_frozen' in col]
            if frozen_cols:
                st.subheader("⚠️ 凍結資料檢測")
                for col in frozen_cols:
                    frozen_count = df_clean[col].sum()
                    if frozen_count > 0:
                        st.warning(f"{col.replace('_frozen', '')}: {frozen_count} 筆凍結資料")
            
            st.session_state['batch_df_clean'] = df_clean
            
        except Exception as e:
            st.error(f"❌ 清洗錯誤: {str(e)}")
            st.exception(e)


def _render_stats_tab():
    """渲染統計資訊標籤頁"""
    st.header("統計資訊")
    
    df = _get_current_df()
    if df is None:
        st.info("請先在「解析資料」分頁解析檔案")
        return
    
    # Data status indicator
    if 'batch_df_clean' in st.session_state:
        st.info("📊 **目前分析：清洗後資料** (已重採樣並過濾異常值)")
    else:
        st.info("📊 **目前分析：解析後資料** (原始資料)")
    
    numeric_cols = get_analysis_numeric_cols(df)
    
    if numeric_cols:
        selected_col = st.selectbox("選擇欄位", numeric_cols)
        
        if selected_col:
            _show_column_stats(df, selected_col)
    else:
        st.info("沒有數值欄位可供分析")


def _render_timeseries_tab():
    """渲染時間序列標籤頁"""
    st.header("時間序列分析")
    
    df = _get_current_df()
    if df is None:
        st.info("請先在「解析資料」分頁解析檔案")
        return
    
    # Data status indicator
    if 'batch_df_clean' in st.session_state:
        st.info("📊 **目前分析：清洗後資料**")
    else:
        st.info("📊 **目前分析：解析後資料**")
    
    if 'timestamp' not in df.columns:
        st.error("資料中沒有 timestamp 欄位")
        return
    
    numeric_cols = get_analysis_numeric_cols(df)
    
    if not numeric_cols:
        st.warning("沒有數值欄位可供分析")
        return
    
    st.subheader("選擇欄位進行時間序列分析")
    
    selected_cols = st.multiselect(
        "選擇要顯示的欄位（最多3個）",
        numeric_cols,
        default=[numeric_cols[0]] if numeric_cols else [],
        max_selections=3
    )
    
    if selected_cols:
        pandas_df = df.select(['timestamp'] + selected_cols).to_pandas()
        pandas_df = pandas_df.set_index('timestamp')
        
        st.line_chart(pandas_df)
        
        st.caption(f"時間範圍: {df['timestamp'].min()} 至 {df['timestamp'].max()}")
        st.caption(f"資料點數: {len(df):,}")
    else:
        st.info("請至少選擇一個欄位")


def _render_correlation_tab():
    """渲染關聯矩陣標籤頁"""
    st.header("🔗 關聯矩陣熱圖")
    
    df = _get_current_df()
    if df is None:
        st.info("請先在「解析資料」分頁解析檔案")
        return
    
    # Data status indicator
    if 'batch_df_clean' in st.session_state:
        st.info("📊 **目前分析：清洗後資料**")
    else:
        st.info("📊 **目前分析：解析後資料**")
    
    from .components import show_correlation_heatmap
    show_correlation_heatmap(df)


def _render_quality_tab():
    """渲染資料品質標籤頁"""
    st.header("🎯 資料品質儀表板")
    
    df = _get_current_df()
    if df is None:
        st.info("請先在「解析資料」分頁解析檔案")
        return
    
    # Data status indicator
    if 'batch_df_clean' in st.session_state:
        st.info("📊 **目前分析：清洗後資料**")
    else:
        st.info("📊 **目前分析：解析後資料**")
    
    from .components import show_quality_dashboard, show_physics_validation_status, show_frozen_data_detection
    from .components import calculate_quality_score, show_quality_score
    
    # Overall quality metrics
    show_quality_dashboard(df)
    
    # Physics validation
    st.markdown("---")
    show_physics_validation_status(df)
    
    # Frozen data detection
    if 'batch_df_clean' in st.session_state:
        st.markdown("---")
        show_frozen_data_detection(df)
    
    # Quality score
    st.markdown("---")
    quality_score = calculate_quality_score(df)
    show_quality_score(quality_score)


def _render_export_tab():
    """渲染匯出標籤頁"""
    st.header("匯出資料")
    
    has_parsed = 'batch_merged_df' in st.session_state
    has_clean = 'batch_df_clean' in st.session_state
    
    if not has_parsed and not has_clean:
        st.info("請先在「解析資料」分頁解析檔案")
        return
    
    export_type = st.radio(
        "選擇匯出資料",
        ["解析後資料", "清洗後資料（如已清洗）"]
    )
    
    df_to_export = None
    if export_type == "解析後資料" and has_parsed:
        df_to_export = st.session_state['batch_merged_df']
    elif export_type == "清洗後資料（如已清洗）" and has_clean:
        df_to_export = st.session_state['batch_df_clean']
    
    if df_to_export is not None:
        show_export_buttons(df_to_export, "hvac_batch")
    else:
        st.warning("請先清洗資料或選擇解析後資料匯出")


def _get_current_df():
    """獲取當前使用的 DataFrame（優先使用清洗後的）"""
    if 'batch_df_clean' in st.session_state:
        return st.session_state['batch_df_clean']
    elif 'batch_merged_df' in st.session_state:
        return st.session_state['batch_merged_df']
    return None


def _show_column_stats(df: pl.DataFrame, selected_col: str):
    """顯示單一欄位統計資訊"""
    import numpy as np
    
    col_data = df[selected_col]
    col_data_clean = col_data.drop_nulls()
    
    # Metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("平均值", f"{col_data_clean.mean():.2f}")
    with col2:
        st.metric("中位數", f"{col_data_clean.median():.2f}")
    with col3:
        st.metric("最小值", f"{col_data_clean.min():.2f}")
    with col4:
        st.metric("最大值", f"{col_data_clean.max():.2f}")
    with col5:
        st.metric("標準差", f"{col_data_clean.std():.2f}")
    
    # Distribution
    st.subheader("數值分布")
    
    pandas_data = col_data_clean.to_pandas()
    
    if len(pandas_data) > 0:
        counts, bin_edges = np.histogram(pandas_data, bins=30)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        import pandas as pd
        hist_df = pd.DataFrame({
            'value': bin_centers,
            'count': counts
        }).set_index('value')
        
        if hist_df['count'].sum() > 0:
            st.bar_chart(hist_df)
        else:
            st.info("資料範圍太小，無法產生分布圖")
        
        data_range = col_data_clean.max() - col_data_clean.min()
        st.caption(f"資料範圍: {data_range:.2f} | 非空值數量: {len(pandas_data):,}")
    else:
        st.warning("此欄位沒有有效數值")
