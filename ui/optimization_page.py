"""
最佳化模擬模式頁面
包含特徵映射、即時最佳化、特徵重要性、歷史追蹤、模型訓練
"""

import streamlit as st
import polars as pl
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Try to import ML modules
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from models.energy_model import ChillerEnergyModel
    from optimization.optimizer import ChillerOptimizer, OptimizationContext
    from optimization.history_tracker import OptimizationHistoryTracker, create_record_from_result
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    ChillerEnergyModel = None
    ChillerOptimizer = None
    OptimizationContext = None

# Try to import feature mapping
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from config.feature_mapping_v2 import FeatureMapping, STANDARD_CATEGORIES
    FEATURE_MAPPING_AVAILABLE = True
except ImportError:
    FEATURE_MAPPING_AVAILABLE = False
    FeatureMapping = None
    STANDARD_CATEGORIES = {}


def render_optimization_page(selected_model: Optional[str]):
    """
    渲染最佳化模擬頁面
    
    Args:
        selected_model: 選擇的模型檔案名稱
    """
    st.header("⚡ 能耗最佳化模擬")
    st.markdown("**使用訓練好的模型，找出最省電的變頻器設定**")
    
    if not ML_AVAILABLE:
        st.error("❌ ML 模組無法載入，請確認依賴已安裝")
        return
    
    if not selected_model:
        st.warning("⚠️ 請先在側邊欄選擇一個已訓練的模型")
        return
    
    # Load model
    model_path = Path("models") / selected_model
    
    try:
        model = _load_cached_model(model_path)
        
        # Show model info
        col1, col2, col3 = st.columns(3)
        with col1:
            if model.training_metrics:
                st.metric("模型 MAPE", f"{model.training_metrics.get('mape', 0):.2f}%")
        with col2:
            if model.training_metrics:
                st.metric("模型 R²", f"{model.training_metrics.get('r2', 0):.4f}")
        with col3:
            st.metric("特徵數量", f"{len(model.feature_names)}")
        
        st.success(f"✅ 已載入模型: {selected_model}")
        
        # Create tabs
        opt_tab0, opt_tab1, opt_tab2, opt_tab3, opt_tab4 = st.tabs([
            "🗺️ 特徵映射",
            "🎯 即時最佳化",
            "📊 特徵重要性",
            "📈 歷史追蹤",
            "🔧 模型訓練"
        ])
        
        with opt_tab0:
            _render_feature_mapping_tab(model)
        
        with opt_tab1:
            _render_realtime_optimization_tab(model)
        
        with opt_tab2:
            _render_feature_importance_tab(model)
        
        with opt_tab3:
            _render_history_tracking_tab()
        
        with opt_tab4:
            _render_model_training_tab()
            
    except Exception as e:
        st.error(f"❌ 載入模型失敗: {str(e)}")
        st.exception(e)


@st.cache_resource
def _load_cached_model(model_path: Path):
    """快取載入模型"""
    return ChillerEnergyModel.load_model(str(model_path))


def _render_feature_mapping_tab(model: ChillerEnergyModel):
    """渲染特徵映射標籤頁"""
    st.subheader("🗺️ 特徵映射配置")
    st.caption("將資料欄位對應到模型特徵類別，支援自動識別、手動對應與萬用字元模式")
    
    if not FEATURE_MAPPING_AVAILABLE:
        st.error("特徵映射模組無法載入")
        return
    
    # Check if batch data is available
    df_for_mapping = None
    if 'df_clean' in st.session_state:
        df_for_mapping = st.session_state['df_clean']
    elif 'df_parsed' in st.session_state:
        df_for_mapping = st.session_state['df_parsed']
    elif 'batch_merged_df' in st.session_state:
        df_for_mapping = st.session_state['batch_merged_df']
    elif 'batch_df_clean' in st.session_state:
        df_for_mapping = st.session_state['batch_df_clean']
    
    if df_for_mapping is None:
        st.info("📊 請先在批次處理模式解析資料，或上傳 CSV 檔案")
        
        # File upload option
        uploaded = st.file_uploader("上傳 CSV 進行特徵映射", type=['csv'])
        if uploaded:
            try:
                df_for_mapping = pl.read_csv(uploaded)
                st.session_state['uploaded_mapping_df'] = df_for_mapping
                st.success(f"✅ 已上傳: {len(df_for_mapping):,} 筆資料")
                st.rerun()
            except Exception as e:
                st.error(f"讀取檔案失敗: {e}")
        return
    
    # Use the dataframe
    if df_for_mapping is not None:
        available_cols = [c for c in df_for_mapping.columns if c != 'timestamp']
        
        # Initialize session state
        if 'batch_feature_mapping' not in st.session_state:
            st.session_state.batch_feature_mapping = None
        if 'feature_mapping_mode' not in st.session_state:
            st.session_state.feature_mapping_mode = None
        
        st.info(f"📊 可用資料: {len(df_for_mapping):,} 筆，{len(available_cols)} 個欄位")
        
        # --- Mapping Mode Selection ---
        st.markdown("#### 🎛️ 選擇配置方式")
        
        mode_col1, mode_col2, mode_col3 = st.columns(3)
        
        with mode_col1:
            if st.button("🤖 自動識別", 
                        type="primary" if st.session_state.feature_mapping_mode == 'auto' else "secondary",
                        use_container_width=True, key="opt_mode_auto"):
                st.session_state.feature_mapping_mode = 'auto'
                with st.spinner("正在分析欄位名稱..."):
                    auto_mapping = FeatureMapping.create_from_dataframe(available_cols)
                    st.session_state.batch_feature_mapping = auto_mapping
                st.success(f"✅ 自動識別完成！識別到 {len([c for c in auto_mapping.get_all_categories().values() if c])} 個類別")
                st.rerun()
        
        with mode_col2:
            if st.button("✏️ 手動對應",
                        type="primary" if st.session_state.feature_mapping_mode == 'manual' else "secondary",
                        use_container_width=True, key="opt_mode_manual"):
                empty_mapping = FeatureMapping(
                    chilled_water_side={},
                    condenser_water_side={},
                    cooling_tower_system={},
                    environment={},
                    system_level={}
                )
                st.session_state.batch_feature_mapping = empty_mapping
                st.session_state.feature_mapping_mode = 'manual'
                st.rerun()
        
        with mode_col3:
            if st.button("🌟 萬用字元",
                        type="primary" if st.session_state.feature_mapping_mode == 'wildcard' else "secondary",
                        use_container_width=True, key="opt_mode_wildcard"):
                st.session_state.feature_mapping_mode = 'wildcard'
                st.rerun()
        
        # Show mapping editor if mapping exists
        if st.session_state.batch_feature_mapping is not None:
            _render_mapping_editor(st.session_state.batch_feature_mapping, available_cols, df_for_mapping)


def _render_mapping_editor(mapping: Any, available_cols: List[str], df: pl.DataFrame):
    """渲染特徵映射編輯器"""
    st.markdown("---")
    st.markdown("#### 📋 當前映射")
    
    mode_display = {
        'auto': '🤖 自動識別模式',
        'manual': '✏️ 手動對應模式',
        'wildcard': '🌟 萬用字元模式'
    }
    current_mode = st.session_state.get('feature_mapping_mode', 'auto')
    st.markdown(f"**當前模式:** {mode_display.get(current_mode, '自動識別模式')}")
    
    # Summary metrics
    total_features = len(mapping.get_all_feature_cols())
    all_categories = mapping.get_all_categories()
    
    mcol1, mcol2, mcol3 = st.columns(3)
    with mcol1:
        st.metric("總特徵數", total_features)
    with mcol2:
        st.metric("類別數", len([c for c in all_categories.values() if c]))
    with mcol3:
        target_display = mapping.target_col.split('_')[-1] if '_' in mapping.target_col else mapping.target_col
        st.metric("目標變數", target_display)
    
    # Target Variable Selection
    st.markdown("#### 🎯 目標變數 (Target)")
    target_options = [c for c in available_cols if any(kw in c.upper() for kw in ['KW', 'POWER', 'TOTAL', 'COP', 'RT'])]
    if not target_options:
        target_options = available_cols
    
    new_target = st.selectbox(
        "選擇目標欄位",
        options=[""] + target_options,
        index=target_options.index(mapping.target_col) + 1 if mapping.target_col in target_options else 0,
        key="opt_target_select"
    )
    if new_target:
        mapping.target_col = new_target
    
    # Manual Editing Section (only in manual mode)
    if current_mode == 'manual':
        st.markdown("---")
        st.markdown("#### 📝 欄位對應編輯")
        st.caption("展開各系統查看並編輯欄位對應")
        
        all_cats = list(STANDARD_CATEGORIES.keys())
        
        # Group by parent system
        system_groups = {
            "chilled_water_side": {"name": "❄️ 冰水側系統", "categories": []},
            "condenser_water_side": {"name": "🔥 冷卻水側系統", "categories": []},
            "cooling_tower_system": {"name": "🏭 冷卻水塔系統", "categories": []},
            "environment": {"name": "🌍 環境參數", "categories": []},
            "system_level": {"name": "⚡ 系統層級", "categories": []}
        }
        
        for cat_id in all_cats:
            parent = STANDARD_CATEGORIES.get(cat_id, {}).get('parent_system', 'other')
            if parent in system_groups:
                system_groups[parent]["categories"].append(cat_id)
        
        # Create expanders for each system
        for system_id, system_info in system_groups.items():
            cats = system_info["categories"]
            if not cats:
                continue
            
            with st.expander(f"{system_info['name']} ({len(cats)} 類別)", expanded=False):
                for cat_id in cats:
                    cat_info = STANDARD_CATEGORIES.get(cat_id, {})
                    cat_name = cat_info.get('name', cat_id)
                    cat_icon = cat_info.get('icon', '📦')
                    
                    current_cols = mapping.get_category_columns(cat_id)
                    
                    selected_cols = st.multiselect(
                        f"{cat_icon} {cat_name}",
                        options=available_cols,
                        default=current_cols,
                        key=f"opt_manual_select_{cat_id}"
                    )
                    
                    mapping.set_category_columns(cat_id, selected_cols)
    
    # Validation
    st.markdown("---")
    st.markdown("#### ✅ 驗證結果")
    
    validation = mapping.validate_against_dataframe(df.columns)
    if validation['missing_required']:
        st.error(f"❌ 缺少必要欄位: {validation['missing_required']}")
    elif validation['missing_optional']:
        st.warning(f"⚠️ 缺少可選欄位: {validation['missing_optional']}")
    else:
        st.success("✅ 所有映射欄位都存在於資料中")
    
    # Save/Export buttons
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 儲存映射配置"):
            st.session_state['saved_mapping'] = mapping.to_dict()
            st.success("✅ 映射已儲存到 session")
    with col2:
        mapping_json = json.dumps(mapping.to_dict(), indent=2, ensure_ascii=False)
        st.download_button(
            "📥 匯出 JSON",
            mapping_json,
            file_name=f"feature_mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )


def _render_realtime_optimization_tab(model: ChillerEnergyModel):
    """渲染即時最佳化標籤頁"""
    st.subheader("🎯 即時最佳化")
    
    if 'batch_feature_mapping' not in st.session_state or st.session_state.batch_feature_mapping is None:
        st.info("請先在「🗺️ 特徵映射」標籤完成特徵映射配置")
        return
    
    st.info("根據當前工況，計算最佳的變頻器設定組合")
    
    # TODO: Implement real-time optimization UI
    st.caption("此功能需要完整的工況輸入和優化器配置")


def _render_feature_importance_tab(model: ChillerEnergyModel):
    """渲染特徵重要性標籤頁"""
    st.subheader("📊 特徵重要性分析")
    
    if model.feature_importance is not None:
        import pandas as pd
        
        # Sort by importance
        importance_df = model.feature_importance.sort_values('importance', ascending=False)
        
        st.bar_chart(
            importance_df.set_index('feature')['importance'],
            use_container_width=True
        )
        
        st.dataframe(
            importance_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("模型未包含特徵重要性資訊")


def _render_history_tracking_tab():
    """渲染歷史追蹤標籤頁"""
    st.subheader("📈 最佳化歷史追蹤")
    
    history_file = Path("optimization_history.jsonl")
    
    if history_file.exists():
        try:
            tracker = OptimizationHistoryTracker(str(history_file))
            
            # Show summary stats
            stats = tracker.get_summary_stats()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("總記錄數", stats.get('total_records', 0))
            with col2:
                st.metric("最佳 COP", f"{stats.get('best_cop', 0):.3f}")
            with col3:
                st.metric("平均節能", f"{stats.get('avg_energy_saved_percent', 0):.1f}%")
            
            # TODO: Add history visualization
            st.caption("歷史記錄分析功能開發中...")
            
        except Exception as e:
            st.error(f"讀取歷史記錄失敗: {e}")
    else:
        st.info("暫無最佳化歷史記錄")


def _render_model_training_tab():
    """渲染模型訓練標籤頁"""
    st.subheader("🔧 模型訓練")
    
    st.info("在批次處理模式中訓練新模型")
    
    st.markdown("""
    **訓練流程：**
    1. 切換到「📦 批次處理」模式
    2. 解析並清洗資料
    3. 配置特徵映射
    4. 訓練模型
    
    訓練完成後，模型將自動儲存到 `models/` 目錄
    """)
