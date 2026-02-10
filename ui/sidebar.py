"""
側邊欄配置模組 - 二級選單版本
支援展開式的子分頁導航
"""

import streamlit as st
from pathlib import Path


# Define sub-pages for each mode
BATCH_SUBPAGES = [
    ("📋 解析資料", "batch_parse"),
    ("🧹 清洗資料", "batch_clean"),
    ("📊 統計資訊", "batch_stats"),
    ("📈 時間序列", "batch_timeseries"),
    ("🔗 關聯矩陣", "batch_correlation"),
    ("🎯 資料品質", "batch_quality"),
    ("💾 匯出", "batch_export"),
]

OPTIMIZATION_SUBPAGES = [
    ("🗺️ 特徵映射", "opt_mapping"),
    ("🎯 即時最佳化", "opt_realtime"),
    ("📊 特徵重要性", "opt_importance"),
    ("📈 歷史追蹤", "opt_history"),
    ("🔧 模型訓練", "opt_training"),
]


def render_sidebar(ML_AVAILABLE: bool) -> tuple:
    """
    渲染側邊欄配置 - 二級選單版本
    
    Args:
        ML_AVAILABLE: 是否支援機器學習功能
        
    Returns:
        tuple: (processing_mode, selected_files, selected_model, current_page)
    """
    st.sidebar.header("⚙️ 設定")
    
    # Initialize session state for mode and page
    if 'sidebar_mode' not in st.session_state:
        st.session_state.sidebar_mode = "批次處理"
    if 'sidebar_page' not in st.session_state:
        st.session_state.sidebar_page = BATCH_SUBPAGES[0][1]
    
    # Processing mode selection (一级菜单)
    st.sidebar.markdown("### 處理模式")
    
    mode_options = ["批次處理"]
    if ML_AVAILABLE:
        mode_options.append("⚡ 最佳化模擬")
    
    # Mode selection buttons
    mode_cols = st.sidebar.columns(len(mode_options))
    for i, mode in enumerate(mode_options):
        with mode_cols[i]:
            is_active = st.session_state.sidebar_mode == mode
            btn_type = "primary" if is_active else "secondary"
            if st.button(mode, type=btn_type, use_container_width=True, key=f"mode_btn_{mode}"):
                st.session_state.sidebar_mode = mode
                # Reset to first subpage of the new mode
                if mode == "批次處理":
                    st.session_state.sidebar_page = BATCH_SUBPAGES[0][1]
                elif mode == "⚡ 最佳化模擬":
                    st.session_state.sidebar_page = OPTIMIZATION_SUBPAGES[0][1]
                st.rerun()
    
    st.sidebar.markdown("---")
    
    # Sub-page navigation (二级菜单)
    current_mode = st.session_state.sidebar_mode
    
    if current_mode == "批次處理":
        st.sidebar.markdown("### 📦 批次處理選單")
        selected_files = _render_batch_sidebar()
        selected_model = None
        
        # Render subpage buttons
        for page_name, page_key in BATCH_SUBPAGES:
            is_current = st.session_state.sidebar_page == page_key
            btn_type = "primary" if is_current else "secondary"
            if st.sidebar.button(page_name, type=btn_type, use_container_width=True, key=f"page_{page_key}"):
                st.session_state.sidebar_page = page_key
                st.rerun()
                
    elif current_mode == "⚡ 最佳化模擬":
        st.sidebar.markdown("### ⚡ 最佳化模擬選單")
        selected_files = []
        selected_model = _render_optimization_sidebar()
        
        # Render subpage buttons
        for page_name, page_key in OPTIMIZATION_SUBPAGES:
            is_current = st.session_state.sidebar_page == page_key
            btn_type = "primary" if is_current else "secondary"
            if st.sidebar.button(page_name, type=btn_type, use_container_width=True, key=f"page_{page_key}"):
                st.session_state.sidebar_page = page_key
                st.rerun()
    
    return (
        current_mode, 
        selected_files, 
        selected_model, 
        st.session_state.sidebar_page
    )


def _render_batch_sidebar():
    """渲染批次處理側邊欄設定"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("批次處理設定")
    
    data_dir = Path("data/CGMH-TY")
    selected_files = []
    
    if data_dir.exists():
        csv_files = sorted([f.name for f in data_dir.glob("*.csv")])
        st.sidebar.info(f"📁 找到 {len(csv_files)} 個檔案")
        
        # File range selection
        batch_mode_type = st.sidebar.radio(
            "選擇範圍",
            ["全部檔案", "選擇日期範圍"],
            key="batch_range_select"
        )
        
        if batch_mode_type == "選擇日期範圍":
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_idx = st.sidebar.number_input("起始檔案", 0, len(csv_files)-1, 0, key="batch_start")
            with col2:
                end_idx = st.sidebar.number_input("結束檔案", 0, len(csv_files)-1, min(9, len(csv_files)-1), key="batch_end")
            
            selected_files = csv_files[start_idx:end_idx+1]
            st.sidebar.caption(f"選擇了 {len(selected_files)} 個檔案")
        else:
            selected_files = csv_files
        
        # Clear batch data button
        if st.session_state.get('batch_processing_complete', False):
            st.sidebar.markdown("---")
            if st.sidebar.button("🗑️ 清除批次處理資料", type="secondary"):
                st.session_state['batch_processing_complete'] = False
                st.session_state.pop('batch_merged_df', None)
                st.session_state.pop('batch_df_clean', None)
                st.session_state.pop('batch_file_count', None)
                st.session_state.pop('batch_auto_clean', None)
                st.rerun()
    else:
        st.sidebar.error("找不到資料目錄")
    
    return selected_files


def _render_optimization_sidebar():
    """渲染最佳化模擬側邊欄設定"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("模型設定")
    
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)
    
    selected_model = None
    model_files = list(model_dir.glob("*.joblib"))
    
    if model_files:
        model_file_names = [f.name for f in model_files]
        selected_model = st.sidebar.selectbox(
            "選擇已訓練模型",
            model_file_names,
            key="opt_model_select"
        )
        
        # Delete model button
        st.sidebar.markdown("---")
        if st.sidebar.button("🗑️ 刪除選擇的模型", type="secondary"):
            delete_path = model_dir / selected_model
            try:
                delete_path.unlink()
                st.sidebar.success(f"✅ 已刪除: {selected_model}")
                st.sidebar.caption("請重新整理頁面")
                selected_model = None
            except Exception as e:
                st.sidebar.error(f"❌ 刪除失敗: {e}")
    else:
        st.sidebar.warning("尚未訓練模型")
        st.sidebar.caption("請先使用批次處理模式訓練模型")
    
    return selected_model


def get_page_title(page_key: str) -> str:
    """獲取頁面標題"""
    all_pages = {key: name for name, key in BATCH_SUBPAGES + OPTIMIZATION_SUBPAGES}
    return all_pages.get(page_key, "未知頁面")
