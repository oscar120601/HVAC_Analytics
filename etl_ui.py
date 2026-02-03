import streamlit as st
import polars as pl
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from etl.parser import ReportParser
from etl.cleaner import DataCleaner

# Try to import ML modules (may not be available if dependencies missing)
try:
    from models.energy_model import ChillerEnergyModel
    from optimization.optimizer import ChillerOptimizer, OptimizationContext
    from optimization.history_tracker import OptimizationHistoryTracker, create_record_from_result
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# Helper function to get numeric columns for analysis (excluding Date/Time)
def get_analysis_numeric_cols(df):
    """Get numeric columns suitable for statistical analysis, excluding Date/Time/timestamp."""
    # Columns to exclude from analysis
    exclude_cols = {'Date', 'Time', 'timestamp', 'date', 'time'}
    
    numeric_cols = [
        col for col in df.columns 
        if df[col].dtype in [pl.Float32, pl.Float64, pl.Int64, pl.Int32]
        and col not in exclude_cols
    ]
    return numeric_cols

st.set_page_config(
    page_title="HVAC ETL 測試工具",
    page_icon="🏭",
    layout="wide"
)

st.title("🏭 HVAC 冰水系統 - ETL 測試介面")
st.markdown("**資料解析與清洗工具** | Chiller Plant Optimization")

# Sidebar
st.sidebar.header("⚙️ 設定")

# Processing mode selection
mode_options = ["單一檔案", "批次處理（整個資料夾）"]
if ML_AVAILABLE:
    mode_options.append("⚡ 最佳化模擬")

processing_mode = st.sidebar.radio(
    "處理模式",
    mode_options,
    help="選擇單一檔案、批次處理或最佳化模擬模式"
)

# File selection based on mode
if processing_mode == "單一檔案":
    # File upload
    uploaded_file = st.sidebar.file_uploader(
        "上傳 CSV 報表檔案",
        type=['csv'],
        help="選擇 TI_ANDY_SCHEDULER_USE_REPORT_*.csv 檔案"
    )
    
    # Or select from data directory
    st.sidebar.markdown("---")
    st.sidebar.subheader("或從現有資料選擇")
    
    data_dir = Path("data/CGMH-TY")
    if data_dir.exists():
        csv_files = sorted([f.name for f in data_dir.glob("*.csv")])
        selected_file = st.sidebar.selectbox(
            "選擇檔案",
            [""] + csv_files
        )
    else:
        selected_file = None
        st.sidebar.warning("找不到資料目錄")
    selected_files = []

elif processing_mode == "批次處理（整個資料夾）":
    # Batch mode
    uploaded_file = None
    selected_file = None
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("批次處理設定")
    
    data_dir = Path("data/CGMH-TY")
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
                start_idx = st.number_input("起始檔案", 0, len(csv_files)-1, 0)
            with col2:
                end_idx = st.number_input("結束檔案", 0, len(csv_files)-1, min(9, len(csv_files)-1))
            
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
        selected_files = []

elif processing_mode == "⚡ 最佳化模擬":
    # Optimization mode
    uploaded_file = None
    selected_file = None
    selected_files = []
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("模型設定")
    
    # Model file selection
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)
    
    model_files = list(model_dir.glob("*.joblib"))
    if model_files:
        model_file_names = [f.name for f in model_files]
        selected_model = st.sidebar.selectbox(
            "選擇已訓練模型",
            model_file_names
        )
    else:
        selected_model = None
        st.sidebar.warning("尚未訓練模型")
        st.sidebar.caption("請先使用批次處理模式訓練模型")

else:
    uploaded_file = None
    selected_file = None
    selected_files = []

# Main content
# Main content
if processing_mode == "單一檔案" and (uploaded_file or selected_file):
    file_path = None
    
    if uploaded_file:
        # Save uploaded file temporarily
        temp_path = Path(f"/tmp/{uploaded_file.name}")
        with open(temp_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        file_path = str(temp_path)
        st.success(f"✅ 已上傳: {uploaded_file.name}")
    elif selected_file:
        file_path = str(data_dir / selected_file)
        st.success(f"✅ 已選擇: {selected_file}")
    
    # Tabs for different views
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
        st.header("原始資料解析")
        
        try:
            with st.spinner("正在解析報表..."):
                parser = ReportParser()
                df_parsed = parser.parse_file(file_path)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("總列數", f"{len(df_parsed):,}")
            with col2:
                st.metric("總欄位數", f"{len(df_parsed.columns):,}")
            with col3:
                if 'timestamp' in df_parsed.columns:
                    time_range = df_parsed['timestamp'].max() - df_parsed['timestamp'].min()
                    st.metric("時間範圍", f"{time_range}")
            
            st.subheader("資料預覽（前 100 筆）")
            st.dataframe(
                df_parsed.head(100).to_pandas(),
                use_container_width=True,
                height=400
            )
            
            st.subheader("欄位清單")
            col_list = st.columns(4)
            for i, col in enumerate(df_parsed.columns):
                with col_list[i % 4]:
                    st.text(f"• {col}")
            
            # Store in session state for other tabs
            st.session_state['df_parsed'] = df_parsed
            
        except Exception as e:
            st.error(f"❌ 解析錯誤: {str(e)}")
            st.exception(e)
    
    with tab2:
        st.header("資料清洗")
        
        if 'df_parsed' in st.session_state:
            df_parsed = st.session_state['df_parsed']
            
            # Cleaning options
            st.subheader("清洗選項")
            
            # Basic options
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
                            df_parsed,
                            apply_steady_state=apply_steady_state,
                            apply_heat_balance=apply_heat_balance,
                            apply_affinity_laws=apply_affinity,
                            filter_invalid=filter_invalid
                        )
                    
                    st.success(f"✅ 清洗完成！")
                    
                    # Show metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("原始列數", f"{len(df_parsed):,}")
                    with col2:
                        st.metric("清洗後列數", f"{len(df_clean):,}")
                    with col3:
                        retention = len(df_clean) / len(df_parsed) * 100 if len(df_parsed) > 0 else 0
                        st.metric("保留率", f"{retention:.1f}%")
                    
                    # Show validation results
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
                    
                    st.subheader("清洗後資料預覽")
                    st.dataframe(
                        df_clean.head(100).to_pandas(),
                        use_container_width=True,
                        height=400
                    )
                    
                    # Check for frozen data flags
                    frozen_cols = [col for col in df_clean.columns if '_frozen' in col]
                    if frozen_cols:
                        st.subheader("⚠️ 凍結資料檢測")
                        for col in frozen_cols:
                            frozen_count = df_clean[col].sum()
                            if frozen_count > 0:
                                st.warning(f"{col.replace('_frozen', '')}: {frozen_count} 筆凍結資料")
                    
                    st.session_state['df_clean'] = df_clean
                    
                except Exception as e:
                    st.error(f"❌ 清洗錯誤: {str(e)}")
                    st.exception(e)
        else:
            st.info("請先在「解析資料」分頁解析檔案")
    
    with tab3:
        st.header("統計資訊")
        
        if 'df_parsed' in st.session_state:
            df = st.session_state.get('df_clean', st.session_state['df_parsed'])
            
            # Show data status indicator
            if 'df_clean' in st.session_state:
                st.info("📊 **目前分析：清洗後資料** (已重採樣並過濾異常值)")
            else:
                st.info("📊 **目前分析：解析後資料** (原始資料)")
            
            # Select numeric columns for stats (excluding Date/Time)
            numeric_cols = get_analysis_numeric_cols(df)
            
            if numeric_cols:
                selected_col = st.selectbox("選擇欄位", numeric_cols)
                
                if selected_col:
                    col_data = df[selected_col]
                    
                    # Filter out nulls for statistics
                    col_data_clean = col_data.drop_nulls()
                    
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
                    
                    # Distribution visualization
                    st.subheader("數值分布")
                    
                    # Convert to pandas for histogram
                    pandas_data = col_data_clean.to_pandas()
                    
                    if len(pandas_data) > 0:
                        # Create histogram using numpy
                        import numpy as np
                        
                        # Calculate histogram bins
                        counts, bin_edges = np.histogram(pandas_data, bins=30)
                        
                        # Create bin labels (using bin centers)
                        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
                        
                        # Create dataframe for plotting
                        import pandas as pd
                        hist_df = pd.DataFrame({
                            'value': bin_centers,
                            'count': counts
                        }).set_index('value')
                        
                        if hist_df['count'].sum() > 0:
                            st.bar_chart(hist_df)
                        else:
                            st.info("資料範圍太小，無法產生分布圖")
                        
                        # Show data range info
                        data_range = col_data_clean.max() - col_data_clean.min()
                        st.caption(f"資料範圍: {data_range:.2f} | 非空值數量: {len(pandas_data):,}")
                    else:
                        st.warning("此欄位沒有有效數值")
            else:
                st.info("沒有數值欄位可供分析")
        else:
            st.info("請先在「解析資料」分頁解析檔案")
    
    with tab4:
        st.header("時間序列分析")
        
        if 'df_parsed' in st.session_state:
            df = st.session_state.get('df_clean', st.session_state['df_parsed'])
            
            # Show data status indicator
            if 'df_clean' in st.session_state:
                st.info("📊 **目前分析：清洗後資料**")
            else:
                st.info("📊 **目前分析：解析後資料**")
            
            # Check if timestamp exists
            if 'timestamp' in df.columns:
                # Select numeric columns (excluding Date/Time)
                numeric_cols = get_analysis_numeric_cols(df)
                
                if numeric_cols:
                    st.subheader("選擇欄位進行時間序列分析")
                    
                    # Multi-select for comparison
                    selected_cols = st.multiselect(
                        "選擇要顯示的欄位（最多3個）",
                        numeric_cols,
                        default=[numeric_cols[0]] if numeric_cols else [],
                        max_selections=3
                    )
                    
                    if selected_cols:
                        # Create time series chart
                        pandas_df = df.select(['timestamp'] + selected_cols).to_pandas()
                        pandas_df = pandas_df.set_index('timestamp')
                        
                        st.line_chart(pandas_df)
                        
                        # Show data summary
                        st.caption(f"時間範圍: {df['timestamp'].min()} 至 {df['timestamp'].max()}")
                        st.caption(f"資料點數: {len(df):,}")
                    else:
                        st.info("請至少選擇一個欄位")
                else:
                    st.warning("沒有數值欄位可供分析")
            else:
                st.error("資料中沒有 timestamp 欄位")
        else:
            st.info("請先在「解析資料」分頁解析檔案")
    
# 單一檔案 tab5 和 tab6 的內容

    with tab5:
        st.header("🔗 關聯矩陣熱圖")
        
        if 'df_parsed' in st.session_state:
            df = st.session_state.get('df_clean', st.session_state['df_parsed'])
            
            # Show data status indicator
            if 'df_clean' in st.session_state:
                st.info("📊 **目前分析：清洗後資料**")
            else:
                st.info("📊 **目前分析：解析後資料**")
            
            numeric_cols = get_analysis_numeric_cols(df)
            
            if numeric_cols:
                st.subheader("選擇變數進行相關性分析")
                
                # Let user select variables (max 15 for readability)
                max_vars = min(15, len(numeric_cols))
                selected_vars = st.multiselect(
                    f"選擇要分析的變數（最多 {max_vars} 個，建議 5-10 個）",
                    numeric_cols,
                    default=numeric_cols[:min(8, len(numeric_cols))],
                    max_selections=max_vars
                )
                
                if len(selected_vars) >= 2:
                    try:
                        # Calculate correlation matrix
                        import plotly.figure_factory as ff
                        import numpy as np
                        
                        # Extract data and convert to pandas
                        corr_df = df.select(selected_vars).to_pandas()
                        
                        # Calculate correlation matrix
                        corr_matrix = corr_df.corr()
                        
                        # Create heatmap using plotly
                        fig = ff.create_annotated_heatmap(
                            z=corr_matrix.values,
                            x=list(corr_matrix.columns),
                            y=list(corr_matrix.index),
                            annotation_text=np.around(corr_matrix.values, decimals=2),
                            colorscale='RdBu',
                            zmid=0,
                            showscale=True
                        )
                        
                        fig.update_layout(
                            title="變數相關性矩陣",
                            xaxis_title="",
                            yaxis_title="",
                            height=600,
                            xaxis={'side': 'bottom'}
                        )
                        
                        # Rotate x-axis labels
                        fig.update_xaxes(tickangle=45)
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Show interpretation guide
                        st.markdown("---")
                        st.subheader("📖 相關係數解讀")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown("**🔴 強負相關**: -1.0 ~ -0.7")
                            st.caption("一個變數增加時，另一個明顯減少")
                        with col2:
                            st.markdown("**⚪ 無相關**: -0.3 ~ 0.3")
                            st.caption("兩變數之間無明顯線性關係")
                        with col3:
                            st.markdown("**🔵 強正相關**: 0.7 ~ 1.0")
                            st.caption("一個變數增加時，另一個也增加")
                        
                        # Highlight strong correlations
                        st.markdown("---")
                        st.subheader("🎯 顯著相關性（|r| > 0.7）")
                        
                        strong_corr = []
                        for i in range(len(corr_matrix)):
                            for j in range(i+1, len(corr_matrix)):
                                corr_val = corr_matrix.iloc[i, j]
                                if abs(corr_val) > 0.7:
                                    var1 = corr_matrix.index[i]
                                    var2 = corr_matrix.columns[j]
                                    strong_corr.append({
                                        '變數 1': var1,
                                        '變數 2': var2,
                                        '相關係數': f"{corr_val:.3f}",
                                        '類型': '正相關 🔵' if corr_val > 0 else '負相關 🔴'
                                    })
                        
                        if strong_corr:
                            import pandas as pd
                            st.dataframe(pd.DataFrame(strong_corr), use_container_width=True)
                        else:
                            st.info("沒有發現強相關性（|r| > 0.7）的變數對")
                    
                    except Exception as e:
                        st.error(f"計算相關性失敗: {str(e)}")
                        st.exception(e)
                else:
                    st.warning("請至少選擇 2 個變數進行相關性分析")
            else:
                st.warning("沒有數值欄位可供分析")
        else:
            st.info("請先在「解析資料」分頁解析檔案")
    
    with tab6:
        st.header("🎯 資料品質儀表板")
        
        if 'df_parsed' in st.session_state:
            df = st.session_state.get('df_clean', st.session_state['df_parsed'])
            
            # Show data status indicator
            if 'df_clean' in st.session_state:
                st.info("📊 **目前分析：清洗後資料**")
            else:
                st.info("📊 **目前分析：解析後資料**")
            
            # Overall quality metrics
            st.subheader("📈 整體資料品質")
            
            total_rows = len(df)
            total_cols = len(df.columns)
            numeric_cols = get_analysis_numeric_cols(df)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("總列數", f"{total_rows:,}")
            with col2:
                st.metric("總欄位數", f"{total_cols}")
            with col3:
                st.metric("數值欄位", f"{len(numeric_cols)}")
            with col4:
                if 'timestamp' in df.columns:
                    time_span = df['timestamp'].max() - df['timestamp'].min()
                    st.metric("時間跨度", str(time_span))
            
            # Missing data analysis
            st.markdown("---")
            st.subheader("🔍 缺失值分析")
            
            # Columns to exclude from missing value analysis (Date/Time related)
            exclude_missing_cols = {'Date', 'Time', 'timestamp', 'date', 'time'}
            
            missing_data = []
            for col in df.columns:
                # Skip Date/Time columns
                if col in exclude_missing_cols:
                    continue
                null_count = df[col].null_count()
                if null_count > 0:
                    null_pct = (null_count / total_rows) * 100
                    missing_data.append({
                        '欄位名稱': col,
                        '缺失數量': null_count,
                        '缺失比例': f"{null_pct:.2f}%",
                        '嚴重程度': '🔴 高' if null_pct > 30 else ('🟡 中' if null_pct > 10 else '🟢 低')
                    })
            
            if missing_data:
                import pandas as pd
                missing_df = pd.DataFrame(missing_data).sort_values('缺失數量', ascending=False)
                st.dataframe(missing_df, use_container_width=True)
                
                # Visualize missing data
                import plotly.express as px
                fig = px.bar(
                    missing_df.head(10),
                    x='欄位名稱',
                    y='缺失數量',
                    title='前 10 個缺失值最多的欄位',
                    labels={'缺失數量': '缺失數量', '欄位名稱': '欄位'}
                )
                fig.update_layout(xaxis_tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("✅ 沒有缺失值！")
            
            # Frozen data detection (only if cleaned)
            if 'df_clean' in st.session_state:
                st.markdown("---")
                st.subheader("❄️ 凍結資料偵測")
                
                frozen_cols = [col for col in df.columns if '_frozen' in col]
                
                if frozen_cols:
                    frozen_summary = []
                    for col in frozen_cols:
                        original_col = col.replace('_frozen', '')
                        frozen_count = df[col].sum()
                        if frozen_count > 0:
                            frozen_pct = (frozen_count / total_rows) * 100
                            frozen_summary.append({
                                '感測器': original_col,
                                '凍結點數': frozen_count,
                                '凍結比例': f"{frozen_pct:.2f}%",
                                '狀態': '🔴 警告' if frozen_pct > 5 else '🟡 注意'
                            })
                    
                    if frozen_summary:
                        import pandas as pd
                        frozen_df = pd.DataFrame(frozen_summary).sort_values('凍結點數', ascending=False)
                        st.dataframe(frozen_df, use_container_width=True)
                        
                        st.warning("⚠️ 凍結資料可能表示感測器故障或數據傳輸問題")
                    else:
                        st.success("✅ 沒有偵測到凍結資料")
                else:
                    st.info("資料中無凍結標記欄位")
            else:
                st.info("尚未執行凍結資料偵測（需先清洗資料）")
            
            # Physics Validation Status Section
            st.markdown("---")
            st.subheader("🔬 物理驗證狀態")
            
            validation_cols = st.columns(3)
            
            with validation_cols[0]:
                st.markdown("**📊 穩態檢測**")
                if 'is_steady_state' in df.columns:
                    steady_count = df['is_steady_state'].sum()
                    total_count = len(df)
                    steady_pct = (steady_count / total_count * 100) if total_count > 0 else 0
                    st.metric("穩態資料", f"{steady_count:,} ({steady_pct:.1f}%)")
                    
                    # Small bar chart
                    steady_data = {'狀態': ['穩態', '非穩態'], '數量': [steady_count, total_count - steady_count]}
                    import pandas as pd
                    st.bar_chart(pd.DataFrame(steady_data).set_index('狀態'))
                else:
                    st.caption("未執行穩態檢測")
            
            with validation_cols[1]:
                st.markdown("**🌡️ 熱平衡驗證**")
                if 'heat_balance_invalid' in df.columns:
                    invalid_count = df['heat_balance_invalid'].sum()
                    total_count = len(df)
                    invalid_pct = (invalid_count / total_count * 100) if total_count > 0 else 0
                    st.metric("異常資料", f"{invalid_count:,} ({invalid_pct:.1f}%)")
                    
                    if invalid_pct > 20:
                        st.error("🔴 異常比例過高")
                    elif invalid_pct > 10:
                        st.warning("🟡 異常比例中等")
                    else:
                        st.success("🟢 異常比例正常")
                else:
                    st.caption("未執行熱平衡驗證")
            
            with validation_cols[2]:
                st.markdown("**⚡ 親和力定律檢查**")
                if 'affinity_law_invalid' in df.columns:
                    invalid_count = df['affinity_law_invalid'].sum()
                    total_count = len(df)
                    invalid_pct = (invalid_count / total_count * 100) if total_count > 0 else 0
                    st.metric("異常資料", f"{invalid_count:,} ({invalid_pct:.1f}%)")
                    
                    # Show affinity ratio distribution if available
                    if 'affinity_ratio' in df.columns:
                        ratio_data = df['affinity_ratio'].drop_nulls()
                        if len(ratio_data) > 0:
                            st.caption(f"比率範圍: {ratio_data.min():.4f} ~ {ratio_data.max():.4f}")
                else:
                    st.caption("未執行親和力定律檢查")
            
            # Data completeness timeline
            if 'timestamp' in df.columns and numeric_cols:
                st.markdown("---")
                st.subheader("📅 資料完整性時間軸")
                
                # Select a representative column to check completeness
                sample_col = st.selectbox(
                    "選擇欄位檢視完整性",
                    numeric_cols
                )
                
                if sample_col:
                    # Create a binary completeness indicator
                    timeline_df = df.select(['timestamp', sample_col]).to_pandas()
                    timeline_df['完整性'] = (~timeline_df[sample_col].isna()).astype(int)
                    timeline_df = timeline_df.set_index('timestamp')
                    
                    import plotly.graph_objects as go
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=timeline_df.index,
                        y=timeline_df['完整性'],
                        mode='lines',
                        fill='tozeroy',
                        name='資料存在',
                        line=dict(color='green')
                    ))
                    
                    fig.update_layout(
                        title=f"{sample_col} 資料完整性時間軸",
                        xaxis_title="時間",
                        yaxis_title="資料存在 (1=有, 0=無)",
                        height=300,
                        yaxis=dict(tickvals=[0, 1], ticktext=['缺失', '存在'])
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
            
            # Data quality score
            st.markdown("---")
            st.subheader("⭐ 整體品質評分")
            
            # Calculate quality score (0-100)
            quality_score = 100
            
            # Deduct points for missing data
            if missing_data:
                avg_missing_pct = sum([float(d['缺失比例'].strip('%')) for d in missing_data]) / len(df.columns)
                quality_score -= min(avg_missing_pct, 30)
            
            # Deduct points for frozen data (only if cleaned)
            if 'df_clean' in st.session_state:
                frozen_cols = [col for col in df.columns if '_frozen' in col]
                if frozen_cols:
                    frozen_count = sum([df[col].sum() for col in frozen_cols])
                    frozen_pct = (frozen_count / (total_rows * len(frozen_cols))) * 100 if frozen_cols else 0
                    quality_score -= min(frozen_pct, 20)
            
            quality_score = max(0, quality_score)
            
            # Display score with color coding
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.metric("資料品質評分", f"{quality_score:.1f}/100")
            
            with col2:
                if quality_score >= 90:
                    st.success("🟢 優秀")
                elif quality_score >= 75:
                    st.info("🔵 良好")
                elif quality_score >= 60:
                    st.warning("🟡 尚可")
                else:
                    st.error("🔴 需改善")
            
            with col3:
                # Progress bar
                st.progress(quality_score / 100)
            
            # Recommendations
            if quality_score < 90:
                st.markdown("---")
                st.subheader("💡 改善建議")
                
                if missing_data and len(missing_data) > 0:
                    st.markdown("- 檢查缺失比例 > 10% 的欄位，考慮補值或移除")
                
                if 'df_clean' in st.session_state:
                    frozen_cols = [col for col in df.columns if '_frozen' in col]
                    if frozen_cols:
                        frozen_count = sum([df[col].sum() for col in frozen_cols])
                        if frozen_count > 0:
                            st.markdown("- 檢查凍結資料的感測器，可能需要維護")
                
                st.markdown("- 確認資料收集頻率與預期一致")
                st.markdown("- 考慮進行異常值偵測與處理")
        else:
            st.info("請先在「解析資料」分頁解析檔案")

    with tab7:
        st.header("匯出資料")
        
        if 'df_parsed' in st.session_state or 'df_clean' in st.session_state:
            
            export_type = st.radio(
                "選擇匯出資料",
                ["解析後資料", "清洗後資料（如已清洗）"]
            )
            
            df_to_export = None
            if export_type == "解析後資料" and 'df_parsed' in st.session_state:
                df_to_export = st.session_state['df_parsed']
            elif export_type == "清洗後資料（如已清洗）" and 'df_clean' in st.session_state:
                df_to_export = st.session_state['df_clean']
            
            if df_to_export is not None:
                col1, col2 = st.columns(2)
                
                with col1:
                    # CSV export
                    csv_data = df_to_export.write_csv()
                    st.download_button(
                        label="📥 下載 CSV",
                        data=csv_data,
                        file_name=f"hvac_etl_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                
                with col2:
                    # Parquet export (more efficient)
                    # Use BytesIO buffer since write_parquet needs a file
                    from io import BytesIO
                    buffer = BytesIO()
                    df_to_export.write_parquet(buffer)
                    parquet_data = buffer.getvalue()
                    
                    st.download_button(
                        label="📥 下載 Parquet",
                        data=parquet_data,
                        file_name=f"hvac_etl_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet",
                        mime="application/octet-stream"
                    )
                
                st.info("💡 Parquet 格式較小且效能更好，適合大型資料集")
            else:
                st.warning("請先清洗資料或選擇解析後資料匯出")
        else:
            st.info("請先在「解析資料」分頁解析檔案")

elif processing_mode == "批次處理（整個資料夾）" and selected_files:
    st.header("📦 批次處理模式")
    
    st.info(f"準備處理 {len(selected_files)} 個檔案")
    
    # Show file list preview
    with st.expander("查看檔案清單"):
        if len(selected_files) <= 10:
            for f in selected_files:
                st.text(f"• {f}")
        else:
            st.text("前 5 個檔案:")
            for f in selected_files[:5]:
                st.text(f"  • {f}")
            st.text(f"  ... ({len(selected_files) - 10} 個檔案)")
            st.text("後 5 個檔案:")
            for f in selected_files[-5:]:
                st.text(f"  • {f}")
    
    # Processing options
    st.subheader("⚙️ 處理選項")
    
    col1, col2 = st.columns(2)
    with col1:
        batch_resample = st.selectbox("重採樣間隔", ["5m", "10m", "15m", "30m", "1h"], index=0)
    with col2:
        auto_clean = st.checkbox("自動清洗資料", value=True)
    
    # Physics-based validation options (only show if auto_clean is enabled)
    if auto_clean:
        st.subheader("🔬 物理驗證選項")
        col1, col2, col3 = st.columns(3)
        with col1:
            batch_apply_steady_state = st.checkbox("穩態檢測", value=False, 
                help="只保留負載變化小於 5% 的穩態資料")
        with col2:
            batch_apply_heat_balance = st.checkbox("熱平衡驗證", value=False,
                help="驗證 Q = Flow × ΔT 關係")
        with col3:
            batch_apply_affinity = st.checkbox("親和力定律檢查", value=False,
                help="驗證泵浦 Power ∝ Frequency³ 關係")
        
        batch_filter_invalid = st.checkbox("移除無效資料", value=False,
            help="移除未通過上述驗證的資料列")
    
    # Start batch processing
    if st.button("🚀 開始批次處理", type="primary"):
        try:
            from etl.batch_processor import BatchProcessor
            from etl.cleaner import DataCleaner
            
            # Prepare file paths
            file_paths = [str(data_dir / f) for f in selected_files]
            
            # Create processor
            processor = BatchProcessor(resample_interval=batch_resample)
            
            # Progress bar
            status_text = st.empty()
            status_text.text("正在處理檔案...")
            
            if auto_clean:
                # Process files without cleaning first
                with st.spinner("正在解析檔案..."):
                    merged_df = processor.process_files(file_paths, clean=False)
                
                # Apply advanced cleaning with physics validation
                status_text.text("正在執行資料清洗與驗證...")
                with st.spinner("清洗與驗證中..."):
                    cleaner = DataCleaner(resample_interval=batch_resample)
                    merged_df = cleaner.clean_data(
                        merged_df,
                        apply_steady_state=batch_apply_steady_state if auto_clean else False,
                        apply_heat_balance=batch_apply_heat_balance if auto_clean else False,
                        apply_affinity_laws=batch_apply_affinity if auto_clean else False,
                        filter_invalid=batch_filter_invalid if auto_clean else False
                    )
                
                # Store validation results
                st.session_state['batch_validation_results'] = {
                    'steady_state': batch_apply_steady_state if auto_clean else False,
                    'heat_balance': batch_apply_heat_balance if auto_clean else False,
                    'affinity_laws': batch_apply_affinity if auto_clean else False,
                    'filter_invalid': batch_filter_invalid if auto_clean else False
                }
            else:
                with st.spinner("處理中..."):
                    merged_df = processor.process_files(file_paths, clean=False)
                
                st.session_state['batch_validation_results'] = None
            
            status_text.text("處理完成!")
            
            # Store in session state
            if auto_clean:
                st.session_state['df_clean'] = merged_df
                st.session_state['df_parsed'] = merged_df
            else:
                st.session_state['df_parsed'] = merged_df
            
            # Mark batch processing as complete
            st.session_state['batch_processing_complete'] = True
            st.session_state['batch_file_count'] = len(selected_files)
            st.session_state['batch_auto_clean'] = auto_clean
            
        except Exception as e:
            st.error(f"❌ 批次處理錯誤: {str(e)}")
            st.exception(e)
    
    # Show analysis tabs if batch processing is complete (persists across re-renders)
    if st.session_state.get('batch_processing_complete', False):
        # Get data from session state
        if 'df_clean' in st.session_state:
            merged_df = st.session_state['df_clean']
        elif 'df_parsed' in st.session_state:
            merged_df = st.session_state['df_parsed']
        else:
            st.error("資料遺失，請重新執行批次處理")
            if st.button("重置"):
                st.session_state['batch_processing_complete'] = False
                st.rerun()
            st.stop()
        
        batch_file_count = st.session_state.get('batch_file_count', 0)
        auto_clean = st.session_state.get('batch_auto_clean', True)
            
        # Show summary
        st.success(f"✅ 成功處理 {batch_file_count} 個檔案")
        
        # Show validation results if any were applied
        validation_results = st.session_state.get('batch_validation_results')
        if validation_results:
            result_cols = []
            if validation_results.get('steady_state'):
                steady_count = merged_df['is_steady_state'].sum() if 'is_steady_state' in merged_df.columns else 0
                result_cols.append(f"穩態資料: {steady_count} 筆")
            if validation_results.get('heat_balance'):
                invalid_count = merged_df['heat_balance_invalid'].sum() if 'heat_balance_invalid' in merged_df.columns else 0
                result_cols.append(f"熱平衡異常: {invalid_count} 筆")
            if validation_results.get('affinity_laws'):
                invalid_count = merged_df['affinity_law_invalid'].sum() if 'affinity_law_invalid' in merged_df.columns else 0
                result_cols.append(f"親和力定律異常: {invalid_count} 筆")
            
            if result_cols:
                st.info(" | ".join(result_cols))
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("總列數", f"{len(merged_df):,}")
        with col2:
            st.metric("總欄位數", f"{len(merged_df.columns):,}")
        with col3:
            if 'timestamp' in merged_df.columns:
                time_range = merged_df['timestamp'].max() - merged_df['timestamp'].min()
                st.metric("時間範圍", str(time_range))
        
        st.markdown("---")
        st.info("📊 **資料已載入！** 請使用下方標籤頁分析合併後的資料")
        
        # Analysis tabs
        batch_tab1, batch_tab2, batch_tab3, batch_tab4, batch_tab5, batch_tab6, batch_tab7 = st.tabs([
            "📋 資料預覽",
            "🧹 清洗資料",
            "📊 統計資訊", 
            "📈 時間序列",
            "🔗 關聯矩陣",
            "🎯 資料品質",
            "💾 匯出"
        ])
            
        with batch_tab1:
            st.subheader("合併後資料預覽")
            st.dataframe(merged_df.head(100).to_pandas(), use_container_width=True)
            st.caption(f"顯示前 100 筆，共 {len(merged_df):,} 筆資料")
        with batch_tab2:
            st.header("🧹 資料清洗")
            
            # Check if we have parsed data to clean
            if 'df_parsed' in st.session_state:
                df_to_clean = st.session_state['df_parsed']
                
                # Cleaning options
                st.subheader("清洗選項")
                
                # Basic options
                col1, col2 = st.columns(2)
                with col1:
                    batch_clean_resample = st.selectbox(
                        "重採樣間隔",
                        ["5m", "10m", "15m", "30m", "1h"],
                        index=0,
                        key="batch_clean_resample"
                    )
                with col2:
                    batch_detect_frozen = st.checkbox("檢測凍結資料", value=True, key="batch_detect_frozen")
                
                # Physics-based validation options
                st.subheader("🔬 物理驗證選項")
                col1, col2, col3 = st.columns(3)
                with col1:
                    batch_reapply_steady_state = st.checkbox("穩態檢測", value=False, 
                        help="只保留負載變化小於 5% 的穩態資料",
                        key="batch_reapply_steady")
                with col2:
                    batch_reapply_heat_balance = st.checkbox("熱平衡驗證", value=False,
                        help="驗證 Q = Flow × ΔT 關係",
                        key="batch_reapply_heat")
                with col3:
                    batch_reapply_affinity = st.checkbox("親和力定律檢查", value=False,
                        help="驗證泵浦 Power ∝ Frequency³ 關係",
                        key="batch_reapply_affinity")
                
                # Filter options
                batch_refilter_invalid = st.checkbox("移除無效資料", value=False,
                    help="移除未通過上述驗證的資料列",
                    key="batch_refilter_invalid")
                
                if st.button("🧹 開始清洗", type="primary", key="batch_clean_button"):
                    try:
                        with st.spinner("正在清洗資料..."):
                            cleaner = DataCleaner(resample_interval=batch_clean_resample)
                            df_cleaned = cleaner.clean_data(
                                df_to_clean,
                                apply_steady_state=batch_reapply_steady_state,
                                apply_heat_balance=batch_reapply_heat_balance,
                                apply_affinity_laws=batch_reapply_affinity,
                                filter_invalid=batch_refilter_invalid
                            )
                        
                        st.success(f"✅ 清洗完成！")
                        
                        # Show metrics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("原始列數", f"{len(df_to_clean):,}")
                        with col2:
                            st.metric("清洗後列數", f"{len(df_cleaned):,}")
                        with col3:
                            retention = len(df_cleaned) / len(df_to_clean) * 100 if len(df_to_clean) > 0 else 0
                            st.metric("保留率", f"{retention:.1f}%")
                        
                        # Show validation results
                        validation_results = []
                        if batch_reapply_steady_state and "is_steady_state" in df_cleaned.columns:
                            steady_count = df_cleaned["is_steady_state"].sum()
                            validation_results.append(f"穩態資料: {steady_count} 筆")
                        if batch_reapply_heat_balance and "heat_balance_invalid" in df_cleaned.columns:
                            invalid_count = df_cleaned["heat_balance_invalid"].sum()
                            validation_results.append(f"熱平衡異常: {invalid_count} 筆")
                        if batch_reapply_affinity and "affinity_law_invalid" in df_cleaned.columns:
                            invalid_count = df_cleaned["affinity_law_invalid"].sum()
                            validation_results.append(f"親和力定律異常: {invalid_count} 筆")
                        
                        if validation_results:
                            st.info(" | ".join(validation_results))
                        
                        # Show frozen data detection
                        frozen_cols = [col for col in df_cleaned.columns if '_frozen' in col]
                        if frozen_cols:
                            st.subheader("⚠️ 凍結資料檢測")
                            for col in frozen_cols:
                                frozen_count = df_cleaned[col].sum()
                                if frozen_count > 0:
                                    st.warning(f"{col.replace('_frozen', '')}: {frozen_count} 筆凍結資料")
                        
                        # Update session state
                        st.session_state['df_clean'] = df_cleaned
                        merged_df = df_cleaned  # Update local reference
                        
                        st.subheader("清洗後資料預覽")
                        st.dataframe(
                            df_cleaned.head(100).to_pandas(),
                            use_container_width=True,
                            height=400
                        )
                        
                    except Exception as e:
                        st.error(f"❌ 清洗錯誤: {str(e)}")
                        st.exception(e)
                
                # Show current cleaning status
                if auto_clean and not batch_reapply_steady_state and not batch_reapply_heat_balance and not batch_reapply_affinity:
                    st.markdown("---")
                    st.success("✅ 批次處理時已自動執行基礎清洗（重採樣、濕球溫度、凍結檢測）")
                    
            else:
                st.error("❌ 沒有可清洗的資料")
                st.info("請先執行批次處理或載入資料")
            
        with batch_tab3:
            st.subheader("統計資訊")
            
            # Show data status
            if auto_clean:
                st.info("📊 **目前分析：清洗後資料** (已重採樣並過濾異常值)")
            else:
                st.info("📊 **目前分析：解析後資料** (原始資料)")
            
            # Select numeric columns (excluding Date/Time)
            numeric_cols = get_analysis_numeric_cols(merged_df)
            
            if numeric_cols:
                selected_col = st.selectbox("選擇欄位", numeric_cols, key="batch_stats_col")
                
                if selected_col:
                    col_data_clean = merged_df[selected_col].drop_nulls()
                    
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        mean_val = col_data_clean.mean()
                        st.metric("平均值", f"{mean_val:.2f}" if mean_val is not None else "N/A")
                    with col2:
                        median_val = col_data_clean.median()
                        st.metric("中位數", f"{median_val:.2f}" if median_val is not None else "N/A")
                    with col3:
                        min_val = col_data_clean.min()
                        st.metric("最小值", f"{min_val:.2f}" if min_val is not None else "N/A")
                    with col4:
                        max_val = col_data_clean.max()
                        st.metric("最大值", f"{max_val:.2f}" if max_val is not None else "N/A")
                    with col5:
                        std_val = col_data_clean.std()
                        st.metric("標準差", f"{std_val:.2f}" if std_val is not None else "N/A")
                    
                    # Distribution
                    st.subheader("數值分布")
                    pandas_data = col_data_clean.to_pandas()
                    
                    if len(pandas_data) > 0:
                        import numpy as np
                        import pandas as pd
                        
                        counts, bin_edges = np.histogram(pandas_data, bins=30)
                        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
                        hist_df = pd.DataFrame({'value': bin_centers, 'count': counts}).set_index('value')
                        
                        if hist_df['count'].sum() > 0:
                            st.bar_chart(hist_df)
                        
                        data_range = col_data_clean.max() - col_data_clean.min()
                        st.caption(f"資料範圍: {data_range:.2f} | 非空值數量: {len(pandas_data):,}")
            else:
                st.warning("沒有數值欄位可供分析")
            
        with batch_tab4:
            st.subheader("時間序列分析")
            
            if 'timestamp' in merged_df.columns:
                numeric_cols = get_analysis_numeric_cols(merged_df)
                
                if numeric_cols:
                    selected_cols = st.multiselect(
                        "選擇要顯示的欄位（最多3個）",
                        numeric_cols,
                        default=[numeric_cols[0]] if numeric_cols else [],
                        max_selections=3,
                        key="batch_timeseries_cols"
                    )
                    
                    if selected_cols:
                        pandas_df = merged_df.select(['timestamp'] + selected_cols).to_pandas()
                        pandas_df = pandas_df.set_index('timestamp')
                        st.line_chart(pandas_df)
                        
                        st.caption(f"時間範圍: {merged_df['timestamp'].min()} 至 {merged_df['timestamp'].max()}")
                        st.caption(f"資料點數: {len(merged_df):,}")
                    else:
                        st.info("請至少選擇一個欄位")
                else:
                    st.warning("沒有數值欄位可供分析")
            else:
                st.error("資料中沒有 timestamp 欄位")
            

        with batch_tab5:
            st.header("🔗 關聯矩陣熱圖")
            
            if auto_clean:
                st.info("📊 **目前分析：清洗後資料**")
            else:
                st.info("📊 **目前分析：解析後資料**")
            
            numeric_cols = get_analysis_numeric_cols(merged_df)
            
            if numeric_cols:
                st.subheader("選擇變數進行相關性分析")
                
                max_vars = min(15, len(numeric_cols))
                selected_vars = st.multiselect(
                    f"選擇要分析的變數（最多 {max_vars} 個，建議 5-10 個）",
                    numeric_cols,
                    default=numeric_cols[:min(8, len(numeric_cols))],
                    max_selections=max_vars,
                    key="batch_corr_vars"
                )
                
                if len(selected_vars) >= 2:
                    try:
                        import plotly.figure_factory as ff
                        import numpy as np
                        
                        corr_df = merged_df.select(selected_vars).to_pandas()
                        corr_matrix = corr_df.corr()
                        
                        fig = ff.create_annotated_heatmap(
                            z=corr_matrix.values,
                            x=list(corr_matrix.columns),
                            y=list(corr_matrix.index),
                            annotation_text=np.around(corr_matrix.values, decimals=2),
                            colorscale='RdBu',
                            zmid=0,
                            showscale=True
                        )
                        
                        fig.update_layout(
                            title="變數相關性矩陣",
                            height=600,
                            xaxis={'side': 'bottom'}
                        )
                        fig.update_xaxes(tickangle=45)
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.markdown("---")
                        st.subheader("📖 相關係數解讀")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown("**🔴 強負相關**: -1.0 ~ -0.7")
                        with col2:
                            st.markdown("**⚪ 無相關**: -0.3 ~ 0.3")
                        with col3:
                            st.markdown("**🔵 強正相關**: 0.7 ~ 1.0")
                        
                    except Exception as e:
                        st.error(f"計算相關性失敗: {str(e)}")
                else:
                    st.warning("請至少選擇 2 個變數進行相關性分析")
            else:
                st.warning("沒有數值欄位可供分析")
        
        with batch_tab6:
            st.header("🎯 資料品質儀表板")
            
            if auto_clean:
                st.info("📊 **目前分析：清洗後資料**")
            else:
                st.info("📊 **目前分析：解析後資料**")
            
            st.subheader("📈 整體資料品質")
            
            total_rows = len(merged_df)
            total_cols = len(merged_df.columns)
            numeric_cols = get_analysis_numeric_cols(merged_df)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("總列數", f"{total_rows:,}")
            with col2:
                st.metric("總欄位數", f"{total_cols}")
            with col3:
                st.metric("數值欄位", f"{len(numeric_cols)}")
            with col4:
                if 'timestamp' in merged_df.columns:
                    time_span = merged_df['timestamp'].max() - merged_df['timestamp'].min()
                    st.metric("時間跨度", str(time_span))
            
            st.markdown("---")
            st.subheader("🔍 缺失值分析")
            
            # Columns to exclude from missing value analysis (Date/Time related)
            exclude_missing_cols = {'Date', 'Time', 'timestamp', 'date', 'time'}
            
            missing_data = []
            for col in merged_df.columns:
                # Skip Date/Time columns
                if col in exclude_missing_cols:
                    continue
                null_count = merged_df[col].null_count()
                if null_count > 0:
                    null_pct = (null_count / total_rows) * 100
                    missing_data.append({
                        '欄位名稱': col,
                        '缺失數量': null_count,
                        '缺失比例': f"{null_pct:.2f}%",
                        '嚴重程度': '🔴 高' if null_pct > 30 else ('🟡 中' if null_pct > 10 else '🟢 低')
                    })
            
            if missing_data:
                import pandas as pd
                missing_df = pd.DataFrame(missing_data).sort_values('缺失數量', ascending=False)
                st.dataframe(missing_df, use_container_width=True)
                
                # Visualize missing data
                import plotly.express as px
                fig = px.bar(
                    missing_df.head(10),
                    x='欄位名稱',
                    y='缺失數量',
                    title='前 10 個缺失值最多的欄位',
                    labels={'缺失數量': '缺失數量', '欄位名稱': '欄位'}
                )
                fig.update_layout(xaxis_tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("✅ 沒有缺失值！")
            
            # Physics Validation Status Section
            st.markdown("---")
            st.subheader("🔬 物理驗證狀態")
            
            validation_cols = st.columns(3)
            
            with validation_cols[0]:
                st.markdown("**📊 穩態檢測**")
                if 'is_steady_state' in merged_df.columns:
                    steady_count = merged_df['is_steady_state'].sum()
                    total_count = len(merged_df)
                    steady_pct = (steady_count / total_count * 100) if total_count > 0 else 0
                    st.metric("穩態資料", f"{steady_count:,} ({steady_pct:.1f}%)")
                    
                    # Small bar chart
                    steady_data = {'狀態': ['穩態', '非穩態'], '數量': [steady_count, total_count - steady_count]}
                    import pandas as pd
                    st.bar_chart(pd.DataFrame(steady_data).set_index('狀態'))
                else:
                    st.caption("未執行穩態檢測")
            
            with validation_cols[1]:
                st.markdown("**🌡️ 熱平衡驗證**")
                if 'heat_balance_invalid' in merged_df.columns:
                    invalid_count = merged_df['heat_balance_invalid'].sum()
                    total_count = len(merged_df)
                    invalid_pct = (invalid_count / total_count * 100) if total_count > 0 else 0
                    st.metric("異常資料", f"{invalid_count:,} ({invalid_pct:.1f}%)")
                    
                    if invalid_pct > 20:
                        st.error("🔴 異常比例過高")
                    elif invalid_pct > 10:
                        st.warning("🟡 異常比例中等")
                    else:
                        st.success("🟢 異常比例正常")
                else:
                    st.caption("未執行熱平衡驗證")
            
            with validation_cols[2]:
                st.markdown("**⚡ 親和力定律檢查**")
                if 'affinity_law_invalid' in merged_df.columns:
                    invalid_count = merged_df['affinity_law_invalid'].sum()
                    total_count = len(merged_df)
                    invalid_pct = (invalid_count / total_count * 100) if total_count > 0 else 0
                    st.metric("異常資料", f"{invalid_count:,} ({invalid_pct:.1f}%)")
                    
                    # Show affinity ratio distribution if available
                    if 'affinity_ratio' in merged_df.columns:
                        ratio_data = merged_df['affinity_ratio'].drop_nulls()
                        if len(ratio_data) > 0:
                            st.caption(f"比率範圍: {ratio_data.min():.4f} ~ {ratio_data.max():.4f}")
                else:
                    st.caption("未執行親和力定律檢查")
            
            # Frozen data detection summary
            st.markdown("---")
            st.subheader("❄️ 凍結資料檢測")
            
            if auto_clean:
                frozen_cols = [col for col in merged_df.columns if '_frozen' in col]
                
                if frozen_cols:
                    frozen_summary = []
                    for col in frozen_cols:
                        original_col = col.replace('_frozen', '')
                        frozen_count = merged_df[col].sum()
                        if frozen_count > 0:
                            frozen_pct = (frozen_count / total_rows) * 100
                            frozen_summary.append({
                                '感測器': original_col,
                                '凍結點數': frozen_count,
                                '凍結比例': f"{frozen_pct:.2f}%",
                                '狀態': '🔴 警告' if frozen_pct > 5 else '🟡 注意'
                            })
                    
                    if frozen_summary:
                        import pandas as pd
                        frozen_df = pd.DataFrame(frozen_summary).sort_values('凍結點數', ascending=False)
                        st.dataframe(frozen_df, use_container_width=True)
                        
                        st.warning("⚠️ 凍結資料可能表示感測器故障或數據傳輸問題")
                    else:
                        st.success("✅ 沒有偵測到凍結資料")
                else:
                    st.info("資料中無凍結標記欄位")
            else:
                st.info("尚未執行凍結資料偵測（需先清洗資料）")
            
            # Data completeness timeline
            if 'timestamp' in merged_df.columns and numeric_cols:
                st.markdown("---")
                st.subheader("📅 資料完整性時間軸")
                
                # Select a representative column to check completeness
                sample_col = st.selectbox(
                    "選擇欄位檢視完整性",
                    numeric_cols,
                    key="batch_completeness_col"
                )
                
                if sample_col:
                    # Create a binary completeness indicator
                    timeline_df = merged_df.select(['timestamp', sample_col]).to_pandas()
                    timeline_df['完整性'] = (~timeline_df[sample_col].isna()).astype(int)
                    timeline_df = timeline_df.set_index('timestamp')
                    
                    import plotly.graph_objects as go
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=timeline_df.index,
                        y=timeline_df['完整性'],
                        mode='lines',
                        fill='tozeroy',
                        name='資料存在',
                        line=dict(color='green')
                    ))
                    
                    fig.update_layout(
                        title=f"{sample_col} 資料完整性時間軸",
                        xaxis_title="時間",
                        yaxis_title="資料存在 (1=有, 0=無)",
                        height=300,
                        yaxis=dict(tickvals=[0, 1], ticktext=['缺失', '存在'])
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
            
            # Data quality score
            st.markdown("---")
            st.subheader("⭐ 整體品質評分")
            
            # Calculate quality score (0-100)
            quality_score = 100
            
            # Deduct points for missing data
            if missing_data:
                avg_missing_pct = sum([float(d['缺失比例'].strip('%')) for d in missing_data]) / len(merged_df.columns)
                quality_score -= min(avg_missing_pct, 30)
            
            # Deduct points for frozen data (only if cleaned)
            if auto_clean:
                frozen_cols = [col for col in merged_df.columns if '_frozen' in col]
                if frozen_cols:
                    frozen_count = sum([merged_df[col].sum() for col in frozen_cols])
                    frozen_pct = (frozen_count / (total_rows * len(frozen_cols))) * 100 if frozen_cols else 0
                    quality_score -= min(frozen_pct, 20)
            
            quality_score = max(0, quality_score)
            
            # Display score with color coding
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.metric("資料品質評分", f"{quality_score:.1f}/100")
            
            with col2:
                if quality_score >= 90:
                    st.success("🟢 優秀")
                elif quality_score >= 75:
                    st.info("🔵 良好")
                elif quality_score >= 60:
                    st.warning("🟡 尚可")
                else:
                    st.error("🔴 需改善")
            
            with col3:
                # Progress bar
                st.progress(quality_score / 100)
            
            # Recommendations
            if quality_score < 90:
                st.markdown("---")
                st.subheader("💡 改善建議")
                
                if missing_data and len(missing_data) > 0:
                    st.markdown("- 檢查缺失比例 > 10% 的欄位，考慮補值或移除")
                
                if auto_clean:
                    frozen_cols = [col for col in merged_df.columns if '_frozen' in col]
                    if frozen_cols:
                        frozen_count = sum([merged_df[col].sum() for col in frozen_cols])
                        if frozen_count > 0:
                            st.markdown("- 檢查凍結資料的感測器，可能需要維護")
                
                st.markdown("- 確認資料收集頻率與預期一致")
                st.markdown("- 考慮進行異常值偵測與處理")

        with batch_tab7:
            st.header("匯出資料")
            
            # Data selection radio (matching single file mode)
            export_type = st.radio(
                "選擇匯出資料",
                ["解析後資料", "清洗後資料（如已清洗）"],
                key="batch_export_type"
            )
            
            df_to_export = None
            if export_type == "解析後資料" and 'df_parsed' in st.session_state:
                df_to_export = st.session_state['df_parsed']
                st.info("📊 **匯出：解析後資料**（原始合併資料）")
            elif export_type == "清洗後資料（如已清洗）" and 'df_clean' in st.session_state:
                df_to_export = st.session_state['df_clean']
                st.info("📊 **匯出：清洗後資料**（已重採樣並過濾異常值）")
            
            if df_to_export is not None:
                col1, col2 = st.columns(2)
                
                with col1:
                    # CSV export
                    csv_data = df_to_export.write_csv()
                    st.download_button(
                        label="📥 下載 CSV",
                        data=csv_data,
                        file_name=f"hvac_batch_{batch_file_count}files_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                
                with col2:
                    # Parquet export
                    from io import BytesIO
                    buffer = BytesIO()
                    df_to_export.write_parquet(buffer)
                    parquet_data = buffer.getvalue()
                    
                    st.download_button(
                        label="📥 下載 Parquet",
                        data=parquet_data,
                        file_name=f"hvac_batch_{batch_file_count}files_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet",
                        mime="application/octet-stream"
                    )
                
                st.info("💡 Parquet 格式較小且效能更好，適合大型資料集")
            else:
                if export_type == "清洗後資料（如已清洗）":
                    st.warning("請先執行資料清洗或選擇「解析後資料」")
                else:
                    st.warning("沒有可匯出的資料")

elif processing_mode == "⚡ 最佳化模擬" and ML_AVAILABLE:
    # Optimization Simulation Mode
    st.header("⚡ 能耗最佳化模擬")
    st.markdown("**使用訓練好的模型，找出最省電的變頻器設定**")
    
    # Check if model is selected
    if 'selected_model' in dir() and selected_model:
        model_path = Path("models") / selected_model
        
        # Load model
        @st.cache_resource
        def load_model(path):
            return ChillerEnergyModel.load_model(str(path))
        
        try:
            model = load_model(model_path)
            
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
            
            # Create tabs for different functions
            opt_tab1, opt_tab2, opt_tab3, opt_tab4 = st.tabs([
                "🎯 即時最佳化",
                "📊 特徵重要性",
                "📈 歷史追蹤",
                "🔧 模型訓練"
            ])
            
            with opt_tab1:
                st.subheader("設定當前運轉條件")
                
                # Input parameters
                st.markdown("#### 🏭 負載條件")
                col1, col2 = st.columns(2)
                with col1:
                    load_rt = st.slider(
                        "冷凍噸負載 (RT)",
                        min_value=100,
                        max_value=2000,
                        value=500,
                        step=50,
                        help="當前的冷卻負載"
                    )
                with col2:
                    temp_db_out = st.slider(
                        "室外乾球溫度 (°C)",
                        min_value=15.0,
                        max_value=40.0,
                        value=30.0,
                        step=0.5,
                        help="當前室外溫度"
                    )
                
                st.markdown("#### ⚙️ 當前變頻器設定")
                col1, col2, col3 = st.columns(3)
                with col1:
                    current_chw_pump_hz = st.slider(
                        "冰水泵頻率 (Hz)",
                        min_value=30.0,
                        max_value=60.0,
                        value=50.0,
                        step=1.0,
                        help="CHP 變頻器輸出"
                    )
                with col2:
                    current_cw_pump_hz = st.slider(
                        "冷卻水泵頻率 (Hz)",
                        min_value=30.0,
                        max_value=60.0,
                        value=50.0,
                        step=1.0,
                        help="CWP 變頻器輸出"
                    )
                with col3:
                    current_ct_fan_hz = st.slider(
                        "冷卻塔風扇頻率 (Hz)",
                        min_value=30.0,
                        max_value=60.0,
                        value=50.0,
                        step=1.0,
                        help="CT 變頻器輸出"
                    )
                
                st.markdown("---")
                
                # Optimization options
                col1, col2 = st.columns(2)
                with col1:
                    opt_method = st.radio(
                        "最佳化方法",
                        ["SLSQP (快速)", "Differential Evolution (全域)"],
                        help="SLSQP 適合快速求解，DE 適合尋找全域最佳解"
                    )
                
                # Run optimization button
                if st.button("🚀 執行最佳化", type="primary", use_container_width=True):
                    with st.spinner("正在計算最佳設定..."):
                        # Create context
                        context = OptimizationContext(
                            load_rt=load_rt,
                            temp_db_out=temp_db_out,
                            current_chw_pump_hz=current_chw_pump_hz,
                            current_cw_pump_hz=current_cw_pump_hz,
                            current_ct_fan_hz=current_ct_fan_hz
                        )
                        
                        # Create optimizer
                        optimizer = ChillerOptimizer(model)
                        
                        # Run optimization
                        if "SLSQP" in opt_method:
                            result = optimizer.optimize_slsqp(context)
                        else:
                            result = optimizer.optimize_global(context, maxiter=50)
                        
                        # Store result and context in session state for persistence
                        st.session_state['last_optimization_result'] = result
                        st.session_state['last_optimization_context'] = {
                            'load_rt': load_rt,
                            'temp_db_out': temp_db_out,
                            'current_chw_pump_hz': current_chw_pump_hz,
                            'current_cw_pump_hz': current_cw_pump_hz,
                            'current_ct_fan_hz': current_ct_fan_hz,
                            'opt_method': opt_method,
                            'model_name': selected_model
                        }
                        st.session_state['optimization_saved'] = False
                
                # Display results if available in session state
                if 'last_optimization_result' in st.session_state and st.session_state['last_optimization_result'] is not None:
                    result = st.session_state['last_optimization_result']
                    ctx = st.session_state.get('last_optimization_context', {})
                    
                    # Display results
                    st.markdown("---")
                    st.subheader("📊 最佳化結果")
                    
                    if result.success:
                        st.success("✅ 最佳化成功完成！")
                    else:
                        st.warning(f"⚠️ {result.message}")
                    
                    # Comparison table
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("##### 🔧 變頻器設定")
                        import pandas as pd
                        settings_df = pd.DataFrame({
                            '項目': ['冰水泵 (Hz)', '冷卻水泵 (Hz)', '冷卻塔風扇 (Hz)'],
                            '目前設定': [
                                ctx.get('current_chw_pump_hz', '-'),
                                ctx.get('current_cw_pump_hz', '-'),
                                ctx.get('current_ct_fan_hz', '-')
                            ],
                            '建議設定': [
                                f"{result.optimal_chw_pump_hz:.1f}",
                                f"{result.optimal_cw_pump_hz:.1f}",
                                f"{result.optimal_ct_fan_hz:.1f}"
                            ]
                        })
                        st.dataframe(settings_df, hide_index=True, use_container_width=True)
                    
                    with col2:
                        st.markdown("##### ⚡ 能耗比較")
                        st.metric(
                            "目前預估能耗",
                            f"{result.baseline_power_kw:.1f} kW"
                        )
                        st.metric(
                            "最佳化後能耗",
                            f"{result.predicted_power_kw:.1f} kW",
                            delta=f"-{result.savings_kw:.1f} kW" if result.savings_kw > 0 else f"+{-result.savings_kw:.1f} kW",
                            delta_color="inverse"
                        )
                    
                    with col3:
                        st.markdown("##### 💰 節能效益")
                        st.metric(
                            "節能比例",
                            f"{result.savings_percent:.1f}%"
                        )
                        # Estimate annual savings (assuming 8760 hours/year, $0.1/kWh)
                        annual_savings = result.savings_kw * 8760 * 3.5  # TWD per kWh
                        if result.savings_kw > 0:
                            st.metric(
                                "預估年節省",
                                f"NT$ {annual_savings:,.0f}"
                            )
                    
                    # Constraint violations
                    if result.constraint_violations:
                        st.markdown("---")
                        st.warning("⚠️ 限制條件警告")
                        for v in result.constraint_violations:
                            st.caption(f"• {v}")
                    
                    # Save result button - only show if not already saved
                    st.markdown("---")
                    if not st.session_state.get('optimization_saved', False):
                        if st.button("💾 儲存此次結果", key="save_optimization_result"):
                            try:
                                # Initialize history tracker
                                history_tracker = OptimizationHistoryTracker()
                                
                                # Create current and optimal settings dicts
                                current_settings = {
                                    'chw_pump_hz': ctx.get('current_chw_pump_hz', 0),
                                    'cw_pump_hz': ctx.get('current_cw_pump_hz', 0),
                                    'tower_fan_hz': ctx.get('current_ct_fan_hz', 0)
                                }
                                optimal_settings = {
                                    'chw_pump_hz': result.optimal_chw_pump_hz,
                                    'cw_pump_hz': result.optimal_cw_pump_hz,
                                    'tower_fan_hz': result.optimal_ct_fan_hz
                                }
                                
                                # Create record
                                record = create_record_from_result(
                                    model_name=ctx.get('model_name', 'unknown'),
                                    load_rt=ctx.get('load_rt', 0),
                                    outdoor_temp=ctx.get('temp_db_out', 0),
                                    current_settings=current_settings,
                                    optimal_settings=optimal_settings,
                                    current_power=result.baseline_power_kw,
                                    optimal_power=result.predicted_power_kw,
                                    method="SLSQP" if "SLSQP" in ctx.get('opt_method', '') else "Differential Evolution"
                                )
                                
                                # Save record
                                history_tracker.add_record(record)
                                st.session_state['optimization_saved'] = True
                                st.success("✅ 結果已儲存！可在「📈 歷史追蹤」分頁查看。")
                            except Exception as e:
                                st.error(f"儲存失敗: {e}")
                    else:
                        st.info("✅ 此次結果已儲存。執行新的最佳化後可再次儲存。")
            
            with opt_tab2:
                st.subheader("📊 特徵重要性分析")
                
                importance = model.get_feature_importance()
                
                if importance:
                    import pandas as pd
                    import plotly.express as px
                    
                    # Create dataframe
                    importance_df = pd.DataFrame([
                        {'特徵': k, '重要性': v}
                        for k, v in list(importance.items())[:15]
                    ])
                    
                    # Bar chart
                    fig = px.bar(
                        importance_df,
                        x='重要性',
                        y='特徵',
                        orientation='h',
                        title='Top 15 特徵重要性',
                        labels={'重要性': '重要性分數', '特徵': '特徵名稱'}
                    )
                    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Table
                    st.markdown("##### 完整特徵重要性列表")
                    full_importance_df = pd.DataFrame([
                        {'排名': i+1, '特徵': k, '重要性': f"{v:.4f}"}
                        for i, (k, v) in enumerate(importance.items())
                    ])
                    st.dataframe(full_importance_df, hide_index=True, use_container_width=True)
                else:
                    st.info("無法取得特徵重要性")
            
            with opt_tab3:
                st.subheader("📈 最佳化歷史追蹤")
                st.markdown("追蹤過去的最佳化結果並分析節能趨勢")
                
                try:
                    # Load history
                    history_tracker = OptimizationHistoryTracker()
                    records = history_tracker.get_all_records()
                    stats = history_tracker.get_total_savings()
                    
                    if records:
                        # Summary metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("總執行次數", f"{stats['total_runs']} 次")
                        with col2:
                            st.metric("累計節省", f"{stats['total_savings_kw']:.1f} kW")
                        with col3:
                            st.metric("平均節能率", f"{stats['avg_savings_percent']:.1f}%")
                        with col4:
                            st.metric("最高節能率", f"{stats['max_savings_percent']:.1f}%")
                        
                        st.markdown("---")
                        
                        # Trend chart
                        import pandas as pd
                        import plotly.express as px
                        import plotly.graph_objects as go
                        
                        # Prepare data for chart
                        history_df = pd.DataFrame([{
                            '時間': r.timestamp[:16].replace('T', ' '),
                            '節能率 (%)': r.savings_percent,
                            '節省電力 (kW)': r.savings_kw,
                            '負載 (RT)': r.load_rt,
                            '目前能耗 (kW)': r.current_power_kw,
                            '最佳能耗 (kW)': r.optimal_power_kw
                        } for r in records])
                        
                        # Savings trend chart
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=history_df['時間'],
                            y=history_df['節能率 (%)'],
                            mode='lines+markers',
                            name='節能率 (%)',
                            line=dict(color='#00CC96', width=2),
                            marker=dict(size=8)
                        ))
                        fig.update_layout(
                            title='節能率趨勢',
                            xaxis_title='時間',
                            yaxis_title='節能率 (%)',
                            height=350
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Power comparison chart
                        fig2 = go.Figure()
                        fig2.add_trace(go.Bar(
                            x=history_df['時間'],
                            y=history_df['目前能耗 (kW)'],
                            name='目前能耗',
                            marker_color='#EF553B'
                        ))
                        fig2.add_trace(go.Bar(
                            x=history_df['時間'],
                            y=history_df['最佳能耗 (kW)'],
                            name='最佳能耗',
                            marker_color='#00CC96'
                        ))
                        fig2.update_layout(
                            title='能耗比較',
                            xaxis_title='時間',
                            yaxis_title='能耗 (kW)',
                            barmode='group',
                            height=350
                        )
                        st.plotly_chart(fig2, use_container_width=True)
                        
                        # History table
                        st.markdown("##### 詳細紀錄")
                        st.dataframe(
                            history_df[['時間', '負載 (RT)', '目前能耗 (kW)', '最佳能耗 (kW)', '節省電力 (kW)', '節能率 (%)']],
                            hide_index=True,
                            use_container_width=True
                        )
                        
                        # Clear history button
                        st.markdown("---")
                        if st.button("🗑️ 清除所有歷史紀錄", type="secondary"):
                            history_tracker.clear_history()
                            st.success("已清除所有紀錄")
                            st.rerun()
                    else:
                        st.info("📭 尚無歷史紀錄。請先在「🎯 即時最佳化」分頁執行優化並儲存結果。")
                except Exception as e:
                    st.error(f"載入歷史紀錄時發生錯誤: {e}")
            
            with opt_tab4:
                st.subheader("🔧 訓練新模型")
                st.markdown("使用批次處理後的資料訓練能耗預測模型")
                
                # Check if batch data is available
                if 'df_clean' in st.session_state or 'df_parsed' in st.session_state:
                    df_for_training = st.session_state.get('df_clean', st.session_state.get('df_parsed'))
                    
                    st.info(f"📊 可用資料: {len(df_for_training):,} 筆")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        new_model_name = st.text_input(
                            "模型名稱",
                            value=f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        )
                    
                    if st.button("🎓 開始訓練", type="primary"):
                        with st.spinner("正在訓練模型..."):
                            try:
                                new_model = ChillerEnergyModel()
                                metrics = new_model.train(df_for_training)
                                
                                # Save model
                                model_path = f"models/{new_model_name}.joblib"
                                new_model.save_model(model_path)
                                
                                st.success(f"✅ 訓練完成！")
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("MAPE", f"{metrics['mape']:.2f}%")
                                with col2:
                                    st.metric("R²", f"{metrics['r2']:.4f}")
                                with col3:
                                    st.metric("RMSE", f"{metrics['rmse']:.2f}")
                                
                                st.info(f"💾 模型已儲存至: {model_path}")
                                st.caption("重新整理頁面即可選擇新模型")
                                
                            except Exception as e:
                                st.error(f"❌ 訓練失敗: {str(e)}")
                else:
                    st.warning("請先使用「批次處理」模式載入並清洗資料")
                    st.caption("1. 切換到「批次處理」模式")
                    st.caption("2. 選擇檔案並執行批次處理")
                    st.caption("3. 回到此頁面進行模型訓練")
        
        except Exception as e:
            st.error(f"❌ 載入模型失敗: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    else:
        st.warning("👈 請從左側選擇已訓練的模型，或使用下方「模型訓練」分頁訓練新模型")
        
        # Still show tabs so user can train a model
        opt_tab1, opt_tab2, opt_tab3, opt_tab4 = st.tabs([
            "🎯 即時最佳化",
            "📊 特徵重要性",
            "📈 歷史追蹤",
            "🔧 模型訓練"
        ])
        
        with opt_tab1:
            st.info("請先選擇或訓練模型後才能使用即時最佳化功能")
            st.markdown("""
            ### 如何開始？
            
            #### 方法一：使用現有模型
            如果已經有訓練好的模型 (`.joblib` 檔案)，請將它放在 `models/` 資料夾中。
            
            #### 方法二：訓練新模型
            1. 點選上方「🔧 模型訓練」分頁
            2. 若尚無資料，請先切換到「批次處理」模式載入資料
            3. 回到此模式後可直接訓練模型
            """)
        
        with opt_tab2:
            st.info("請先選擇模型才能查看特徵重要性")
        
        with opt_tab3:
            st.subheader("📈 最佳化歷史追蹤")
            st.markdown("追蹤過去的最佳化結果並分析節能趨勢")
            
            try:
                # Load history
                history_tracker = OptimizationHistoryTracker()
                records = history_tracker.get_all_records()
                stats = history_tracker.get_total_savings()
                
                if records:
                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("總執行次數", f"{stats['total_runs']} 次")
                    with col2:
                        st.metric("累計節省", f"{stats['total_savings_kw']:.1f} kW")
                    with col3:
                        st.metric("平均節能率", f"{stats['avg_savings_percent']:.1f}%")
                    with col4:
                        st.metric("最高節能率", f"{stats['max_savings_percent']:.1f}%")
                    
                    st.markdown("---")
                    
                    # Prepare data for chart
                    import pandas as pd
                    import plotly.graph_objects as go
                    
                    history_df = pd.DataFrame([{
                        '時間': r.timestamp[:16].replace('T', ' '),
                        '節能率 (%)': r.savings_percent,
                        '節省電力 (kW)': r.savings_kw,
                        '負載 (RT)': r.load_rt,
                        '目前能耗 (kW)': r.current_power_kw,
                        '最佳能耗 (kW)': r.optimal_power_kw
                    } for r in records])
                    
                    # Savings trend chart
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=history_df['時間'],
                        y=history_df['節能率 (%)'],
                        mode='lines+markers',
                        name='節能率 (%)',
                        line=dict(color='#00CC96', width=2),
                        marker=dict(size=8)
                    ))
                    fig.update_layout(
                        title='節能率趨勢',
                        xaxis_title='時間',
                        yaxis_title='節能率 (%)',
                        height=350
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # History table
                    st.markdown("##### 詳細紀錄")
                    st.dataframe(
                        history_df[['時間', '負載 (RT)', '目前能耗 (kW)', '最佳能耗 (kW)', '節省電力 (kW)', '節能率 (%)']],
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Clear history button
                    st.markdown("---")
                    if st.button("🗑️ 清除所有歷史紀錄", type="secondary", key="clear_history_no_model"):
                        history_tracker.clear_history()
                        st.success("已清除所有紀錄")
                        st.rerun()
                else:
                    st.info("📭 尚無歷史紀錄。請先訓練模型並執行優化。")
            except Exception as e:
                st.error(f"載入歷史紀錄時發生錯誤: {e}")
        
        with opt_tab4:
            st.subheader("🔧 訓練新模型")
            st.markdown("使用批次處理後的資料訓練能耗預測模型")
            
            # Check if batch data is available
            if 'df_clean' in st.session_state or 'df_parsed' in st.session_state:
                df_for_training = st.session_state.get('df_clean', st.session_state.get('df_parsed'))
                
                st.info(f"📊 可用資料: {len(df_for_training):,} 筆")
                
                col1, col2 = st.columns(2)
                with col1:
                    new_model_name = st.text_input(
                        "模型名稱",
                        value=f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        key="new_model_name_no_model"
                    )
                
                if st.button("🎓 開始訓練", type="primary", key="train_no_model"):
                    with st.spinner("正在訓練模型..."):
                        try:
                            new_model = ChillerEnergyModel()
                            metrics = new_model.train(df_for_training)
                            
                            # Save model
                            model_path = f"models/{new_model_name}.joblib"
                            new_model.save_model(model_path)
                            
                            st.success(f"✅ 訓練完成！")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("MAPE", f"{metrics['mape']:.2f}%")
                            with col2:
                                st.metric("R²", f"{metrics['r2']:.4f}")
                            with col3:
                                st.metric("RMSE", f"{metrics['rmse']:.2f}")
                            
                            st.info(f"💾 模型已儲存至: {model_path}")
                            st.caption("重新整理頁面即可選擇新模型")
                            
                        except Exception as e:
                            st.error(f"❌ 訓練失敗: {str(e)}")
            else:
                st.warning("請先使用「批次處理」模式載入並清洗資料")
                st.caption("1. 切換到「批次處理」模式")
                st.caption("2. 選擇檔案並執行批次處理")
                st.caption("3. 回到此頁面進行模型訓練")

else:
    # Welcome screen
    st.info("👈 請從左側上傳檔案或選擇現有資料開始")
    
    st.markdown("""
    ### 功能介紹
    
    #### 📋 解析資料
    - 自動解析報表格式的 CSV 檔案
    - 提取 Point 對照表
    - 轉換時間戳記
    
    #### 🧹 清洗資料
    - 重採樣至固定時間間隔（5分鐘/15分鐘等）
    - 計算濕球溫度
    - 偵測凍結資料
    
    #### 📊 統計資訊
    - 查看欄位統計數據
    - 數值分布視覺化
    
    #### 📈 時間序列
    - 多變數趨勢比較
    - 時間範圍分析
    
    #### 💾 匯出
    - CSV 格式
    - Parquet 格式（推薦）
    
    #### 📦 批次處理
    - 一次處理多個檔案
    - 自動合併資料
    - 進度追蹤
    
    #### ⚡ 最佳化模擬 (新功能!)
    - 載入訓練好的能耗預測模型
    - 調整變頻器參數查看預估能耗
    - 自動找出最省電的設定組合
    - 分析特徵重要性
    """)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**HVAC Analytics** | Spec-Kit Implementation")
st.sidebar.caption(f"ETL Pipeline v1.0")
