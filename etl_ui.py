import streamlit as st
import polars as pl
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from etl.parser import ReportParser
from etl.cleaner import DataCleaner

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
processing_mode = st.sidebar.radio(
    "處理模式",
    ["單一檔案", "批次處理（整個資料夾）"],
    help="選擇單一檔案或批次處理模式"
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
else:
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 解析資料", 
        "🧹 清洗資料", 
        "📊 統計資訊", 
        "📈 時間序列",
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
            col1, col2 = st.columns(2)
            
            with col1:
                resample_interval = st.selectbox(
                    "重採樣間隔",
                    ["5m", "10m", "15m", "30m", "1h"],
                    index=0
                )
            
            with col2:
                detect_frozen = st.checkbox("檢測凍結資料", value=True)
            
            if st.button("🧹 開始清洗", type="primary"):
                try:
                    with st.spinner("正在清洗資料..."):
                        cleaner = DataCleaner(resample_interval=resample_interval)
                        df_clean = cleaner.clean_data(df_parsed)
                    
                    st.success(f"✅ 清洗完成！")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("原始列數", f"{len(df_parsed):,}")
                    with col2:
                        st.metric("清洗後列數", f"{len(df_clean):,}")
                    
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
    
    with tab5:
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
    col1, col2 = st.columns(2)
    with col1:
        batch_resample = st.selectbox("重採樣間隔", ["5m", "10m", "15m", "30m", "1h"], index=0)
    with col2:
        auto_clean = st.checkbox("自動清洗資料", value=True)
    
    # Start batch processing
    if st.button("🚀 開始批次處理", type="primary"):
        try:
            from etl.batch_processor import BatchProcessor
            
            # Prepare file paths
            file_paths = [str(data_dir / f) for f in selected_files]
            
            # Create processor
            processor = BatchProcessor(resample_interval=batch_resample)
            
            # Progress bar
            status_text = st.empty()
            status_text.text("正在處理檔案...")
            
            with st.spinner("處理中..."):
                merged_df = processor.process_files(file_paths, clean=auto_clean)
            
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
        batch_tab1, batch_tab2, batch_tab3, batch_tab4 = st.tabs([
            "📋 資料預覽",
            "📊 統計資訊", 
            "📈 時間序列",
            "💾 匯出"
        ])
            
        with batch_tab1:
            st.subheader("合併後資料預覽")
            st.dataframe(merged_df.head(100).to_pandas(), use_container_width=True)
            st.caption(f"顯示前 100 筆，共 {len(merged_df):,} 筆資料")
            
        with batch_tab2:
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
            
        with batch_tab3:
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
            
        with batch_tab4:
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
    """)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**HVAC Analytics** | Spec-Kit Implementation")
st.sidebar.caption(f"ETL Pipeline v1.0")
