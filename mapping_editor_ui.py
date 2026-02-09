"""
Feature Mapping Editor - Streamlit Web UI.

Run with: streamlit run mapping_editor_ui.py
"""

import streamlit as st
import polars as pl
import pandas as pd
import json
from pathlib import Path
from typing import List

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.feature_mapping import FeatureMapping, get_feature_mapping

# Page config
st.set_page_config(
    page_title="特徵映射編輯器 | Feature Mapping Editor",
    page_icon="⚙️",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .category-header {
        font-size: 1.3rem;
        font-weight: bold;
        color: #2ca02c;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }
    .info-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .column-tag {
        display: inline-block;
        padding: 2px 8px;
        margin: 2px;
        border-radius: 12px;
        font-size: 0.85rem;
    }
    .tag-matched {
        background-color: #90EE90;
        color: #006400;
    }
    .tag-missing {
        background-color: #FFB6C1;
        color: #8B0000;
    }
    .tag-available {
        background-color: #FFD700;
        color: #8B4513;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'mapping' not in st.session_state:
        st.session_state.mapping = None
    if 'columns' not in st.session_state:
        st.session_state.columns = []
    if 'df_sample' not in st.session_state:
        st.session_state.df_sample = None


def load_csv_file(file) -> List[str]:
    """Load CSV and return column names."""
    try:
        df = pl.read_csv(file)
        st.session_state.df_sample = df.head(100).to_pandas()
        return df.columns
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return []


def create_feature_card(title: str, columns: List[str], icon: str, help_text: str = ""):
    """Create a card for feature category."""
    with st.expander(f"{icon} {title}", expanded=True):
        st.markdown(f"<small>{help_text}</small>", unsafe_allow_html=True)
        
        # Show current columns as tags
        if columns:
            cols_html = " ".join([
                f'<span class="column-tag tag-matched">{c}</span>'
                for c in columns
            ])
            st.markdown(cols_html, unsafe_allow_html=True)
        else:
            st.info("No columns configured")
        
        return st.multiselect(
            f"Select {title} columns",
            options=st.session_state.columns,
            default=columns,
            key=f"select_{title.lower().replace(' ', '_')}"
        )


def show_validation_results(mapping: FeatureMapping, columns: List[str]):
    """Show validation results."""
    if not mapping or not columns:
        return
    
    result = mapping.validate_against_dataframe(columns)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("✅ Matched", len(result['matched']))
    with col2:
        st.metric("⚠️ Missing (Optional)", len(result['missing_optional']))
    with col3:
        st.metric("❌ Missing (Required)", len(result['missing_required']))
    with col4:
        st.metric("📋 Available", len(result['available_in_df']))
    
    # Show details
    if result['missing_optional']:
        with st.expander("⚠️ Missing Optional Columns"):
            st.write(result['missing_optional'])
    
    if result['missing_required']:
        with st.expander("❌ Missing Required Columns"):
            st.write(result['missing_required'])
    
    if result['available_in_df']:
        with st.expander("📋 Available but Unmapped Columns"):
            st.write(result['available_in_df'])


def main():
    """Main Streamlit app."""
    init_session_state()
    
    # Header
    st.markdown('<div class="main-header">⚙️ 特徵映射編輯器</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Feature Mapping Editor for HVAC Analytics</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("📂 資料來源 (Data Source)")
        
        # Upload CSV
        uploaded_file = st.file_uploader(
            "上傳 CSV 檔案 (Upload CSV)",
            type=['csv'],
            help="上傳一個樣本 CSV 檔案來自動識別欄位"
        )
        
        if uploaded_file:
            if st.button("📖 載入 CSV (Load CSV)"):
                st.session_state.columns = load_csv_file(uploaded_file)
                st.success(f"✅ 載入成功！發現 {len(st.session_state.columns)} 個欄位")
        
        st.divider()
        
        # Predefined mappings
        st.header("🗂️ 預設映射 (Predefined)")
        
        mapping_option = st.selectbox(
            "選擇映射 (Select mapping)",
            ["None", "default", "cgmh_ty", "alternative_01"]
        )
        
        if mapping_option != "None" and st.button("📥 載入預設 (Load)"):
            st.session_state.mapping = get_feature_mapping(mapping_option)
            st.success(f"✅ 已載入 '{mapping_option}' 映射")
        
        st.divider()
        
        # Import/Export
        st.header("💾 匯入/匯出 (Import/Export)")
        
        # Import JSON
        json_file = st.file_uploader("匯入 JSON (Import JSON)", type=['json'])
        if json_file:
            try:
                content = json_file.read().decode('utf-8')
                data = json.loads(content)
                st.session_state.mapping = FeatureMapping(**data)
                st.success("✅ JSON 匯入成功！")
            except Exception as e:
                st.error(f"匯入失敗: {e}")
        
        # Export JSON
        if st.session_state.mapping:
            if st.button("💾 匯出 JSON (Export)"):
                json_str = json.dumps(st.session_state.mapping.to_dict(), indent=2, ensure_ascii=False)
                st.download_button(
                    label="📥 下載 JSON",
                    data=json_str,
                    file_name="feature_mapping.json",
                    mime="application/json"
                )
    
    # Main content
    if not st.session_state.columns and not st.session_state.mapping:
        st.info("""
        👋 歡迎使用特徵映射編輯器！
        
        **開始步驟：**
        1. 在左側上傳 CSV 檔案，或
        2. 載入預設映射
        3. 調整欄位對應
        4. 匯出 JSON 設定檔
        
        **欄位類別說明：**
        - 🏭 **負載 (Load)**: 冷凍機負載 (RT)
        - 💧 **冷凍泵 (CHW Pumps)**: 冷凍水幫浦頻率 (Hz)
        - 🌊 **冷卻泵 (CW Pumps)**: 冷卻水幫浦頻率 (Hz)
        - 🌀 **冷卻塔 (CT Fans)**: 冷卻塔風扇頻率 (Hz)
        - 🌡️ **溫度 (Temperatures)**: 水溫相關 (°C)
        - 🌍 **環境 (Environment)**: 外氣溫度/濕度/濕球溫度
        """)
        return
    
    # Show column info
    if st.session_state.columns:
        with st.expander(f"📋 可用欄位 ({len(st.session_state.columns)} columns)", expanded=False):
            st.write(st.session_state.columns)
            if st.session_state.df_sample is not None:
                st.dataframe(st.session_state.df_sample, use_container_width=True)
    
    # Auto-create mapping button
    if st.session_state.columns and not st.session_state.mapping:
        st.info("檢測到 CSV 欄位，可以自動產生映射或手動設定")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🤖 自動產生映射 (Auto-create)", use_container_width=True):
                with st.spinner("分析欄位中..."):
                    st.session_state.mapping = FeatureMapping.create_from_dataframe(
                        st.session_state.columns
                    )
                st.success("✅ 自動產生完成！請在下方檢查並調整")
                st.rerun()
        
        with col2:
            if st.button("✏️ 手動設定 (Manual)", use_container_width=True):
                st.session_state.mapping = FeatureMapping(
                    load_cols=[],
                    chw_pump_hz_cols=[],
                    cw_pump_hz_cols=[],
                    ct_fan_hz_cols=[],
                    temp_cols=[],
                    env_cols=[],
                    target_col=""
                )
                st.rerun()
    
    # Edit mapping
    if st.session_state.mapping:
        st.markdown("---")
        st.markdown('<div class="category-header">🎯 目標變數 (Target Variable)</div>', unsafe_allow_html=True)
        
        target_col = st.selectbox(
            "選擇目標欄位 (總耗電量 kW)",
            options=[""] + st.session_state.columns,
            index=(st.session_state.columns.index(st.session_state.mapping.target_col) + 1)
            if st.session_state.mapping.target_col in st.session_state.columns else 0,
            key="target_select"
        )
        st.session_state.mapping.target_col = target_col
        
        # Feature categories
        cols = st.columns(2)
        
        with cols[0]:
            st.markdown('<div class="category-header">🏭 負載 (Load / RT)</div>', unsafe_allow_html=True)
            st.markdown("<small>冷凍機製冷負載</small>", unsafe_allow_html=True)
            load_cols = st.multiselect(
                "Select load columns",
                options=st.session_state.columns,
                default=st.session_state.mapping.load_cols,
                label_visibility="collapsed"
            )
            st.session_state.mapping.load_cols = load_cols
            
            st.markdown('<div class="category-header">💧 冷凍泵 (CHW Pumps / Hz)</div>', unsafe_allow_html=True)
            st.markdown("<small>冷凍水幫浦頻率</small>", unsafe_allow_html=True)
            chw_cols = st.multiselect(
                "Select CHW pump columns",
                options=st.session_state.columns,
                default=st.session_state.mapping.chw_pump_hz_cols,
                label_visibility="collapsed"
            )
            st.session_state.mapping.chw_pump_hz_cols = chw_cols
            
            st.markdown('<div class="category-header">🌊 冷卻泵 (CW Pumps / Hz)</div>', unsafe_allow_html=True)
            st.markdown("<small>冷卻水幫浦頻率</small>", unsafe_allow_html=True)
            cw_cols = st.multiselect(
                "Select CW pump columns",
                options=st.session_state.columns,
                default=st.session_state.mapping.cw_pump_hz_cols,
                label_visibility="collapsed"
            )
            st.session_state.mapping.cw_pump_hz_cols = cw_cols
        
        with cols[1]:
            st.markdown('<div class="category-header">🌀 冷卻塔 (CT Fans / Hz)</div>', unsafe_allow_html=True)
            st.markdown("<small>冷卻塔風扇頻率</small>", unsafe_allow_html=True)
            ct_cols = st.multiselect(
                "Select CT fan columns",
                options=st.session_state.columns,
                default=st.session_state.mapping.ct_fan_hz_cols,
                label_visibility="collapsed"
            )
            st.session_state.mapping.ct_fan_hz_cols = ct_cols
            
            st.markdown('<div class="category-header">🌡️ 溫度 (Temperatures / °C)</div>', unsafe_allow_html=True)
            st.markdown("<small>水溫 (SWT/RWT)</small>", unsafe_allow_html=True)
            temp_cols = st.multiselect(
                "Select temperature columns",
                options=st.session_state.columns,
                default=st.session_state.mapping.temp_cols,
                label_visibility="collapsed"
            )
            st.session_state.mapping.temp_cols = temp_cols
            
            st.markdown('<div class="category-header">🌍 環境參數 (Environment)</div>', unsafe_allow_html=True)
            st.markdown("<small>外氣溫度(OAT)/濕度(OAH)/濕球溫度(WBT)</small>", unsafe_allow_html=True)
            env_cols = st.multiselect(
                "Select environment columns",
                options=st.session_state.columns,
                default=getattr(st.session_state.mapping, 'env_cols', []),
                label_visibility="collapsed"
            )
            st.session_state.mapping.env_cols = env_cols
        
        # Validation
        st.markdown("---")
        st.markdown('<div class="category-header">✅ 驗證結果 (Validation)</div>', unsafe_allow_html=True)
        
        if st.session_state.columns:
            show_validation_results(st.session_state.mapping, st.session_state.columns)
        
        # Summary
        st.markdown("---")
        st.markdown('<div class="category-header">📊 映射摘要 (Summary)</div>', unsafe_allow_html=True)
        
        summary_data = {
            "類別 (Category)": [
                "負載 (Load)", "冷凍泵 (CHW)", "冷卻泵 (CW)", 
                "冷卻塔 (CT)", "溫度 (Temp)", "環境 (Env)", "目標 (Target)"
            ],
            "欄位數 (Count)": [
                len(st.session_state.mapping.load_cols),
                len(st.session_state.mapping.chw_pump_hz_cols),
                len(st.session_state.mapping.cw_pump_hz_cols),
                len(st.session_state.mapping.ct_fan_hz_cols),
                len(st.session_state.mapping.temp_cols),
                len(getattr(st.session_state.mapping, 'env_cols', [])),
                1
            ],
            "欄位名稱 (Columns)": [
                ", ".join(st.session_state.mapping.load_cols) or "-",
                ", ".join(st.session_state.mapping.chw_pump_hz_cols) or "-",
                ", ".join(st.session_state.mapping.cw_pump_hz_cols) or "-",
                ", ".join(st.session_state.mapping.ct_fan_hz_cols) or "-",
                ", ".join(st.session_state.mapping.temp_cols) or "-",
                ", ".join(getattr(st.session_state.mapping, 'env_cols', [])) or "-",
                st.session_state.mapping.target_col or "-"
            ]
        }
        
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
        
        # Export section
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.json(st.session_state.mapping.to_dict())
        
        with col2:
            st.markdown("### 💾 儲存")
            filename = st.text_input("檔案名稱", "feature_mapping.json")
            
            json_str = json.dumps(st.session_state.mapping.to_dict(), indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 下載 JSON",
                data=json_str,
                file_name=filename,
                mime="application/json",
                use_container_width=True
            )
            
            st.info("""
            **使用方式：**
            ```bash
            python main.py train data/ --mapping feature_mapping.json
            ```
            """)


if __name__ == "__main__":
    main()
