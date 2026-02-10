"""
側邊欄配置模組
處理所有側邊欄的 UI 元素和設定
"""

import streamlit as st
from pathlib import Path


def render_sidebar(ML_AVAILABLE: bool) -> tuple:
    """
    渲染側邊欄配置
    
    Args:
        ML_AVAILABLE: 是否支援機器學習功能
        
    Returns:
        tuple: (processing_mode, selected_files, selected_model)
    """
    st.sidebar.header("⚙️ 設定")
    
    # Processing mode selection
    mode_options = ["批次處理（整個資料夾）"]
    if ML_AVAILABLE:
        mode_options.append("⚡ 最佳化模擬")
    
    processing_mode = st.sidebar.radio(
        "處理模式",
        mode_options,
        help="選擇批次處理或最佳化模擬模式"
    )
    
    # File/Model selection based on mode
    selected_files = []
    selected_model = None
    
    if processing_mode == "批次處理（整個資料夾）":
        selected_files = _render_batch_sidebar()
    elif processing_mode == "⚡ 最佳化模擬":
        selected_model = _render_optimization_sidebar()
    
    return processing_mode, selected_files, selected_model


def _render_batch_sidebar():
    """渲染批次處理側邊欄"""
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
            ["全部檔案", "選擇日期範圍"]
        )
        
        if batch_mode_type == "選擇日期範圍":
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_idx = st.sidebar.number_input("起始檔案", 0, len(csv_files)-1, 0)
            with col2:
                end_idx = st.sidebar.number_input("結束檔案", 0, len(csv_files)-1, min(9, len(csv_files)-1))
            
            selected_files = csv_files[start_idx:end_idx+1]
            st.sidebar.caption(f"選擇了 {len(selected_files)} 個檔案")
        else:
            selected_files = csv_files
        
        # Clear batch data button
        if st.session_state.get('batch_processing_complete', False):
            st.sidebar.markdown("---")
            if st.sidebar.button("🗑️ 清除批次處理資料", type="secondary"):
                st.session_state['batch_processing_complete'] = False
                st.session_state.pop('batch_file_count', None)
                st.session_state.pop('batch_auto_clean', None)
                st.rerun()
    else:
        st.sidebar.error("找不到資料目錄")
    
    return selected_files


def _render_optimization_sidebar():
    """渲染最佳化模擬側邊欄"""
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
            model_file_names
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
