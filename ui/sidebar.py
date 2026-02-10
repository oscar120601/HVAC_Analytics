"""
側邊欄配置模組 - 美化版本
採用現代化設計風格，支援二級選單導航
"""

import streamlit as st
from pathlib import Path


# Define sub-pages for each mode with icons and colors
BATCH_SUBPAGES = [
    ("📋 解析資料", "batch_parse", "#3498db"),
    ("🧹 清洗資料", "batch_clean", "#e74c3c"),
    ("📊 統計資訊", "batch_stats", "#9b59b6"),
    ("📈 時間序列", "batch_timeseries", "#2ecc71"),
    ("🔗 關聯矩陣", "batch_correlation", "#f39c12"),
    ("🎯 資料品質", "batch_quality", "#1abc9c"),
    ("💾 匯出", "batch_export", "#34495e"),
]

OPTIMIZATION_SUBPAGES = [
    ("🗺️ 特徵映射", "opt_mapping", "#e74c3c"),
    ("🎯 即時最佳化", "opt_realtime", "#3498db"),
    ("📊 特徵重要性", "opt_importance", "#9b59b6"),
    ("📈 歷史追蹤", "opt_history", "#2ecc71"),
    ("🔧 模型訓練", "opt_training", "#f39c12"),
]

# Color schemes
COLORS = {
    "batch_primary": "#3498db",
    "batch_secondary": "#2980b9",
    "opt_primary": "#e74c3c",
    "opt_secondary": "#c0392b",
    "neutral": "#95a5a6",
    "text": "#2c3e50",
    "bg_light": "#f8f9fa",
    "bg_card": "#ffffff",
    "border": "#e0e0e0",
}


def render_sidebar(ML_AVAILABLE: bool) -> tuple:
    """
    渲染美化版側邊欄
    
    Args:
        ML_AVAILABLE: 是否支援機器學習功能
        
    Returns:
        tuple: (processing_mode, selected_files, selected_model, current_page)
    """
    # Apply custom CSS for sidebar styling
    _apply_sidebar_styles()
    
    # Sidebar header with logo style
    st.sidebar.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem 1rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            text-align: center;
        ">
            <h2 style="
                color: white;
                margin: 0;
                font-size: 1.3rem;
                font-weight: 700;
                letter-spacing: 0.5px;
            ">🏭 HVAC Analytics</h2>
            <p style="
                color: rgba(255,255,255,0.9);
                margin: 0.3rem 0 0 0;
                font-size: 0.8rem;
            ">冰水系統 ETL 工具</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'sidebar_mode' not in st.session_state:
        st.session_state.sidebar_mode = "批次處理"
    if 'sidebar_page' not in st.session_state:
        st.session_state.sidebar_page = BATCH_SUBPAGES[0][1]
    
    # Mode selection card
    st.sidebar.markdown("""
        <div style="
            font-size: 0.75rem;
            font-weight: 600;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.8rem;
            padding-left: 0.5rem;
        ">選擇處理模式</div>
    """, unsafe_allow_html=True)
    
    mode_options = ["批次處理"]
    mode_icons = ["📦"]
    mode_colors = [COLORS["batch_primary"]]
    
    if ML_AVAILABLE:
        mode_options.append("⚡ 最佳化模擬")
        mode_icons.append("⚡")
        mode_colors.append(COLORS["opt_primary"])
    
    # Render mode selection cards
    for i, (mode, icon, color) in enumerate(zip(mode_options, mode_icons, mode_colors)):
        is_active = st.session_state.sidebar_mode == mode
        
        # Create card-style button
        card_html = f"""
            <div style="
                background: {'linear-gradient(135deg, ' + color + ' 0%, ' + _darken_color(color, 20) + ' 100%)' if is_active else '#ffffff'};
                border: 2px solid {color if is_active else '#e0e0e0'};
                border-radius: 10px;
                padding: 1rem;
                margin-bottom: 0.8rem;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: {f'0 4px 15px {color}40' if is_active else '0 2px 5px rgba(0,0,0,0.05)'};
            ">
                <div style="
                    font-size: 1.8rem;
                    margin-bottom: 0.3rem;
                    text-align: center;
                ">{icon}</div>
                <div style="
                    color: {'white' if is_active else COLORS['text']};
                    font-weight: {'700' if is_active else '500'};
                    font-size: 0.95rem;
                    text-align: center;
                ">{mode}</div>
            </div>
        """
        
        # Use columns to create clickable cards
        col = st.sidebar.container()
        with col:
            if st.button(
                f"{icon} {mode}", 
                key=f"mode_card_{mode}",
                type="primary" if is_active else "secondary",
                use_container_width=True
            ):
                st.session_state.sidebar_mode = mode
                # Reset to first subpage of the new mode
                if mode == "批次處理":
                    st.session_state.sidebar_page = BATCH_SUBPAGES[0][1]
                elif mode == "⚡ 最佳化模擬":
                    st.session_state.sidebar_page = OPTIMIZATION_SUBPAGES[0][1]
                st.rerun()
    
    st.sidebar.markdown("<hr style='margin: 1.5rem 0; border-color: #e0e0e0;'>", unsafe_allow_html=True)
    
    # Sub-page navigation
    current_mode = st.session_state.sidebar_mode
    
    if current_mode == "批次處理":
        _render_subpage_menu("📦 批次處理選單", BATCH_SUBPAGES, COLORS["batch_primary"])
        selected_files = _render_batch_settings()
        selected_model = None
        
    elif current_mode == "⚡ 最佳化模擬":
        _render_subpage_menu("⚡ 最佳化模擬選單", OPTIMIZATION_SUBPAGES, COLORS["opt_primary"])
        selected_files = []
        selected_model = _render_optimization_settings()
    
    # Footer info card
    st.sidebar.markdown("""
        <div style="
            background: #f8f9fa;
            border-radius: 10px;
            padding: 1rem;
            margin-top: 2rem;
            border: 1px solid #e0e0e0;
        ">
            <div style="
                font-size: 0.75rem;
                color: #7f8c8d;
                text-align: center;
            ">
                <div style="font-weight: 600; margin-bottom: 0.3rem;">HVAC Analytics v2.1</div>
                <div>Modular UI Architecture</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    return (
        current_mode, 
        selected_files, 
        selected_model, 
        st.session_state.sidebar_page
    )


def _render_subpage_menu(title: str, pages: list, primary_color: str):
    """渲染子分頁選單（美化版）"""
    # Section title
    st.sidebar.markdown(f"""
        <div style="
            font-size: 0.75rem;
            font-weight: 600;
            color: {primary_color};
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.8rem;
            padding-left: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        ">
            <span style="font-size: 1rem;">▶</span> {title}
        </div>
    """, unsafe_allow_html=True)
    
    # Render page buttons as styled list
    for page_name, page_key, page_color in pages:
        is_current = st.session_state.sidebar_page == page_key
        
        btn_col1, btn_col2 = st.sidebar.columns([0.15, 0.85])
        
        with btn_col1:
            # Indicator dot
            if is_current:
                st.markdown(f"""
                    <div style="
                        width: 8px;
                        height: 8px;
                        background: {primary_color};
                        border-radius: 50%;
                        margin-top: 0.6rem;
                        box-shadow: 0 0 8px {primary_color}80;
                    "></div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                    <div style="
                        width: 8px;
                        height: 8px;
                        background: #bdc3c7;
                        border-radius: 50%;
                        margin-top: 0.6rem;
                    "></div>
                """, unsafe_allow_html=True)
        
        with btn_col2:
            if st.button(
                page_name,
                key=f"page_{page_key}",
                type="primary" if is_current else "secondary",
                use_container_width=True
            ):
                st.session_state.sidebar_page = page_key
                st.rerun()


def _render_batch_settings():
    """渲染批次處理設定（美化版）"""
    st.sidebar.markdown("<hr style='margin: 1.5rem 0; border-color: #e0e0e0;'>", unsafe_allow_html=True)
    
    # Settings card
    st.sidebar.markdown(f"""
        <div style="
            background: white;
            border: 1px solid {COLORS['border']};
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
        ">
            <div style="
                font-weight: 600;
                color: {COLORS['text']};
                margin-bottom: 1rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            ">
                <span style="font-size: 1.2rem;">⚙️</span> 批次處理設定
            </div>
    """, unsafe_allow_html=True)
    
    data_dir = Path("data/CGMH-TY")
    selected_files = []
    
    if data_dir.exists():
        csv_files = sorted([f.name for f in data_dir.glob("*.csv")])
        
        # File count badge
        st.sidebar.markdown(f"""
            <div style="
                background: {COLORS['batch_primary']}15;
                border-left: 3px solid {COLORS['batch_primary']};
                padding: 0.8rem;
                border-radius: 0 8px 8px 0;
                margin-bottom: 1rem;
            ">
                <div style="font-size: 0.8rem; color: {COLORS['neutral']};">可用檔案</div>
                <div style="font-size: 1.3rem; font-weight: 700; color: {COLORS['batch_primary']};">
                    {len(csv_files)} <span style="font-size: 0.8rem; font-weight: 400;">個 CSV</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Range selection
        batch_mode_type = st.sidebar.radio(
            "選擇範圍",
            ["全部檔案", "選擇日期範圍"],
            key="batch_range_select"
        )
        
        if batch_mode_type == "選擇日期範圍":
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_idx = st.sidebar.number_input(
                    "起始", 0, len(csv_files)-1, 0,
                    key="batch_start"
                )
            with col2:
                end_idx = st.sidebar.number_input(
                    "結束", 0, len(csv_files)-1, min(9, len(csv_files)-1),
                    key="batch_end"
                )
            
            selected_files = csv_files[start_idx:end_idx+1]
            
            # Selection badge
            st.sidebar.markdown(f"""
                <div style="
                    background: #2ecc7115;
                    border-left: 3px solid #2ecc71;
                    padding: 0.6rem 0.8rem;
                    border-radius: 0 8px 8px 0;
                    margin-top: 0.8rem;
                ">
                    <span style="color: #27ae60; font-weight: 600;">✓ 已選擇 {len(selected_files)} 個檔案</span>
                </div>
            """, unsafe_allow_html=True)
        else:
            selected_files = csv_files
        
        # Clear data button
        if st.session_state.get('batch_processing_complete', False):
            st.sidebar.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
            if st.sidebar.button("🗑️ 清除處理資料", type="secondary"):
                st.session_state['batch_processing_complete'] = False
                st.session_state.pop('batch_merged_df', None)
                st.session_state.pop('batch_df_clean', None)
                st.session_state.pop('batch_file_count', None)
                st.session_state.pop('batch_auto_clean', None)
                st.rerun()
    else:
        st.sidebar.error("❌ 找不到資料目錄")
    
    # Close settings card
    st.sidebar.markdown("</div>", unsafe_allow_html=True)
    
    return selected_files


def _render_optimization_settings():
    """渲染最佳化模擬設定（美化版）"""
    st.sidebar.markdown("<hr style='margin: 1.5rem 0; border-color: #e0e0e0;'>", unsafe_allow_html=True)
    
    # Settings card
    st.sidebar.markdown(f"""
        <div style="
            background: white;
            border: 1px solid {COLORS['border']};
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
        ">
            <div style="
                font-weight: 600;
                color: {COLORS['text']};
                margin-bottom: 1rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            ">
                <span style="font-size: 1.2rem;">🤖</span> 模型設定
            </div>
    """, unsafe_allow_html=True)
    
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)
    
    selected_model = None
    model_files = list(model_dir.glob("*.joblib"))
    
    if model_files:
        model_file_names = [f.name for f in model_files]
        
        # Model count badge
        st.sidebar.markdown(f"""
            <div style="
                background: {COLORS['opt_primary']}15;
                border-left: 3px solid {COLORS['opt_primary']};
                padding: 0.8rem;
                border-radius: 0 8px 8px 0;
                margin-bottom: 1rem;
            ">
                <div style="font-size: 0.8rem; color: {COLORS['neutral']};">已訓練模型</div>
                <div style="font-size: 1.3rem; font-weight: 700; color: {COLORS['opt_primary']};">
                    {len(model_files)} <span style="font-size: 0.8rem; font-weight: 400;">個模型</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        selected_model = st.sidebar.selectbox(
            "選擇模型",
            model_file_names,
            key="opt_model_select"
        )
        
        # Delete button
        st.sidebar.markdown("<div style='margin-top: 0.8rem;'></div>", unsafe_allow_html=True)
        if st.sidebar.button("🗑️ 刪除模型", type="secondary"):
            delete_path = model_dir / selected_model
            try:
                delete_path.unlink()
                st.sidebar.success(f"✅ 已刪除: {selected_model}")
                selected_model = None
            except Exception as e:
                st.sidebar.error(f"❌ 刪除失敗: {e}")
    else:
        # No models warning
        st.sidebar.markdown(f"""
            <div style="
                background: #f39c1215;
                border-left: 3px solid #f39c12;
                padding: 0.8rem;
                border-radius: 0 8px 8px 0;
                margin-bottom: 1rem;
            ">
                <div style="font-size: 0.8rem; color: #e67e22;">
                    <span style="font-weight: 600;">⚠️ 尚未訓練模型</span><br>
                    請先使用批次處理模式訓練模型
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    # Close settings card
    st.sidebar.markdown("</div>", unsafe_allow_html=True)
    
    return selected_model


def _apply_sidebar_styles():
    """應用側邊欄 CSS 樣式"""
    st.markdown("""
        <style>
        /* Sidebar background */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
        }
        
        /* Sidebar content padding */
        [data-testid="stSidebar"] > div:first-child {
            padding: 1.5rem 1rem;
        }
        
        /* Button styling */
        .stButton > button {
            border-radius: 8px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
        }
        
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        /* Primary button */
        .stButton > button[kind="primary"] {
            box-shadow: 0 2px 8px rgba(52, 152, 219, 0.3);
        }
        
        /* Secondary button */
        .stButton > button[kind="secondary"] {
            background: white !important;
            border: 1px solid #e0e0e0 !important;
        }
        
        /* Radio button styling */
        .stRadio > div {
            background: white;
            padding: 0.5rem;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        }
        
        /* Number input styling */
        .stNumberInput > div > div > input {
            border-radius: 6px !important;
        }
        
        /* Selectbox styling */
        .stSelectbox > div > div {
            border-radius: 8px !important;
        }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
        }
        
        ::-webkit-scrollbar-track {
            background: #f1f1f1;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #bdc3c7;
            border-radius: 3px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #95a5a6;
        }
        </style>
    """, unsafe_allow_html=True)


def _darken_color(hex_color: str, percent: int) -> str:
    """將顏色變暗指定百分比"""
    # Convert hex to RGB
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    # Darken
    r = max(0, int(r * (100 - percent) / 100))
    g = max(0, int(g * (100 - percent) / 100))
    b = max(0, int(b * (100 - percent) / 100))
    
    # Convert back to hex
    return f"#{r:02x}{g:02x}{b:02x}"


def get_page_title(page_key: str) -> str:
    """獲取頁面標題"""
    all_pages = {key: name for name, key, _ in BATCH_SUBPAGES + OPTIMIZATION_SUBPAGES}
    return all_pages.get(page_key, "未知頁面")
