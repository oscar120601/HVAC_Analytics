"""
🏭 HVAC 冰水系統 - ETL 測試介面

主入口檔案，負責整合所有 UI 模組
"""

import streamlit as st
import sys
from pathlib import Path

# Add src and ui to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

# Try to import ML modules
try:
    from models.energy_model import ChillerEnergyModel
    from optimization.optimizer import ChillerOptimizer, OptimizationContext
    from optimization.history_tracker import OptimizationHistoryTracker, create_record_from_result
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# Import UI modules
from ui.sidebar import render_sidebar
from ui.batch_page import render_batch_page
from ui.optimization_page import render_optimization_page

# Page configuration
st.set_page_config(
    page_title="HVAC ETL 測試工具",
    page_icon="🏭",
    layout="wide"
)

# Title
st.title("🏭 HVAC 冰水系統 - ETL 測試介面")
st.markdown("**資料解析與清洗工具** | Chiller Plant Optimization")

# Render sidebar and get configuration
processing_mode, selected_files, selected_model = render_sidebar(ML_AVAILABLE)

# Main content routing
if processing_mode == "批次處理（整個資料夾）":
    if selected_files:
        render_batch_page(selected_files)
    else:
        st.info("📂 請先在側邊欄選擇資料檔案")
        
elif processing_mode == "⚡ 最佳化模擬" and ML_AVAILABLE:
    render_optimization_page(selected_model)
    
elif processing_mode == "⚡ 最佳化模擬" and not ML_AVAILABLE:
    st.error("❌ ML 模組無法載入")
    st.info("請安裝必要依賴: `pip install xgboost scikit-learn`")

# Footer
st.markdown("---")
st.caption("HVAC Analytics | v2.0 | Modular UI Architecture")
