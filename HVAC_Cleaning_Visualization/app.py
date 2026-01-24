import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
from datetime import datetime, timedelta
from data_parser import merge_datasets
from data_pipeline import run_pipeline, get_cols_by_keyword
from ml_pipeline import FeatureLabeler, AnomalyDetector, EnergyPredictor

st.set_page_config(page_title="HVAC 分析", layout="wide")

# Get list of data folders
DATA_ROOT = "data"
available_projects = [d for d in os.listdir(DATA_ROOT) 
                     if os.path.isdir(os.path.join(DATA_ROOT, d)) 
                     and not d.startswith('.')]

st.sidebar.title("專案設定")
selected_project = st.sidebar.selectbox("選擇專案資料夾", available_projects, index=0 if "Farglory_O3" in available_projects else 0)

@st.cache_data
def load_data(project_folder):
    data_dir = os.path.join(DATA_ROOT, project_folder)
    
    # Load config
    config_path = os.path.join(data_dir, "config.json")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            st.error(f"Error loading config.json: {e}")
            
    df = merge_datasets(data_dir)
    if df is not None:
        df = run_pipeline(df, config=config)
    return df, config

st.title(f"HVAC 資料清洗與視覺化 - {selected_project}")

# Load Data
with st.spinner(f'正在載入 {selected_project} 的數據...'):
    df, config = load_data(selected_project)

if df is None or df.empty:
    st.error(f"在 '{selected_project}' 中未找到數據或解析失敗。")
    st.stop()

# Helper to get keywords from config
def get_keywords(key, default):
    if config and 'tag_keywords' in config:
        return config['tag_keywords'].get(key, default)
    return default

# Sidebar: Filters
st.sidebar.header("篩選條件")

# Ensure index is datetime
if not pd.api.types.is_datetime64_any_dtype(df.index):
    df.index = pd.to_datetime(df.index)

min_date = df.index.min().date()
max_date = df.index.max().date()

start_date = st.sidebar.date_input("開始日期", min_date, min_value=min_date, max_value=max_date)
end_date = st.sidebar.date_input("結束日期", max_date, min_value=min_date, max_value=max_date)

if start_date > end_date:
    st.error("開始日期不能晚於結束日期")
    st.stop()

# Filter data
# Convert date objects to datetime compatible with index for comparison
mask = (df.index.date >= start_date) & (df.index.date <= end_date)
filtered_df = df.loc[mask]

st.sidebar.markdown("---")
st.sidebar.info(f"資料範圍: {min_date} 至 {max_date}")
st.sidebar.info(f"目前顯示: {len(filtered_df)} 筆")

# Export Data
st.sidebar.markdown("---")
st.sidebar.subheader("資料匯出")
csv = filtered_df.to_csv().encode('utf-8')
st.sidebar.download_button(
    label="下載清洗後的資料 (CSV)",
    data=csv,
    file_name=f'{selected_project}_cleaned_data.csv',
    mime='text/csv',
)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["趨勢分析", "關聯性分析", "原始數據", "機器學習"])

with tab1:
    st.subheader("時間序列趨勢")
    
    # 1. Environmental Conditions
    st.markdown("### 1. 環境條件")
    # Use config to find env columns
    kw_oat = get_keywords('out_air_temp', ["OAT"])
    kw_oah = get_keywords('out_air_humidity', ["OAH"])
    
    env_cols = get_cols_by_keyword(filtered_df, kw_oat + kw_oah + ['WetBulb', 'DewPoint'])
    
    if env_cols:
        fig_env = px.line(filtered_df, y=env_cols, title="環境參數趨勢")
        st.plotly_chart(fig_env, use_container_width=True)
    else:
        st.info("未找到環境參數欄位。")
    
    # 2. Power Consumption
    st.markdown("### 2. 電力消耗")
    pwr_col = 'derived_Total_Power'
    if pwr_col in filtered_df.columns:
        fig_pwr = px.line(filtered_df, y=pwr_col, title="總耗電量 (kWh)")
        st.plotly_chart(fig_pwr, use_container_width=True)
    else:
        st.warning("未找到總耗電量欄位。")

    # 3. AHU Details
    st.markdown("### 3. 空調箱 (AHU) 效能")
    # Identify AHUs using Valve/SAT keywords
    kw_valve = get_keywords('valve_opening', [".CV"])
    kw_sat = get_keywords('supply_air_temp', [".SAT"])
    
    ahu_cols = get_cols_by_keyword(filtered_df, kw_valve + kw_sat)
    
    if ahu_cols:
        # Extract AHU prefixes. e.g. "AH01-1.CV" -> "AH01-1"
        # Strategy: split by first occurrence of keyword? Or just split by '.'?
        # Robust way: If keyword is suffix like .CV, split by it.
        # But user config might differ (e.g. "Valve").
        # Simple heuristic: Split by '.' and take first part if '.' exists.
        
        # Or better, just list all available sensor columns and let user pick one?
        # But we want to group them.
        # Let's try getting prefixes.
        prefixes = set()
        for c in ahu_cols:
            if '.' in c:
                prefixes.add(c.rsplit('.', 1)[0])
            else:
                prefixes.add(c) # Fallback
                
        ahus = sorted(list(prefixes))
        
        selected_ahu = st.selectbox("選擇空調箱 / 設備 (AHU)", ahus)
        
        if selected_ahu:
            # Find columns for this AHU that match valve or temp
            ahu_vars = [c for c in filtered_df.columns if c.startswith(selected_ahu)]
            
            if ahu_vars:
                fig_ahu = go.Figure()
                for var in ahu_vars:
                    # Check if it looks like a valve/percentage
                    is_valve = any(k in var for k in kw_valve)
                    
                    if is_valve:
                        fig_ahu.add_trace(go.Scatter(x=filtered_df.index, y=filtered_df[var], name=var + " (%)", yaxis='y2'))
                    else:
                        fig_ahu.add_trace(go.Scatter(x=filtered_df.index, y=filtered_df[var], name=var + " (°C)"))
                
                fig_ahu.update_layout(
                    title=f"{selected_ahu} 趨勢圖",
                    yaxis=dict(title="溫度 (°C)"),
                    yaxis2=dict(title="閥門/百分比 (%)", overlaying='y', side='right', range=[0, 100])
                )
                st.plotly_chart(fig_ahu, use_container_width=True)
    else:
        st.info("未找到關聯的空調箱數據。")

with tab2:
    st.subheader("關聯性分析")
    
    # Scatter: OAT vs Total Power
    if 'derived_Total_Power' in df.columns:
        kw_oat = get_keywords('out_air_temp', ["OAT"])
        oat_cols = get_cols_by_keyword(filtered_df, kw_oat)
        oat_col = oat_cols[0] if oat_cols else None
        
        if oat_col:
            st.markdown("#### 耗電量 vs. 外氣溫度")
            fig_corr = px.scatter(filtered_df, x=oat_col, y='derived_Total_Power', 
                                color=filtered_df.index.hour, 
                                title=f"關聯性: {oat_col} vs 總耗電量",
                                labels={'color': '每日小時'})
            st.plotly_chart(fig_corr, use_container_width=True)
        else:
            st.info("未找到外氣溫度欄位以進行分析。")

    # Scatter: Flow vs Power (Placeholder)
    st.markdown("#### 流量 vs. 耗電量")
    flow_cols = get_cols_by_keyword(filtered_df, ["LPM", "GPM", "Flow"])
    
    if flow_cols and 'derived_Total_Power' in df.columns:
        fig_flow = px.scatter(filtered_df, x=flow_cols[0], y='derived_Total_Power',
                              title="流量 vs 耗電量")
        st.plotly_chart(fig_flow, use_container_width=True)
    else:
        st.info("未偵測到流量計數據或電力數據缺失。")

with tab3:
    st.subheader("數據檢查器")
    st.dataframe(filtered_df.head(100))
    st.markdown("### 缺失值熱圖 (Missing Data Heatmap)")
    st.write(filtered_df.isnull().sum())

with tab4:
    st.subheader("機器學習工具")
    
    # Initialize ML components
    labeler = FeatureLabeler(selected_project, labels_dir='labels')
    
    ml_section = st.radio(
        "選擇功能",
        ["特徵標注", "異常偵測", "能耗預測"],
        horizontal=True
    )
    
    st.markdown("---")
    
    if ml_section == "特徵標注":
        st.markdown("### 特徵標注 (Feature Labeling)")
        st.info("在下方選擇時間範圍並標注該時段的數據狀態")
        
        col1, col2 = st.columns(2)
        with col1:
            label_start = st.date_input(
                "標注開始日期",
                min_date,
                min_value=min_date,
                max_value=max_date,
                key="label_start"
            )
        with col2:
            label_end = st.date_input(
                "標注結束日期",
                max_date,
                min_value=min_date,
                max_value=max_date,
                key="label_end"
            )
        
        label_type = st.selectbox(
            "標籤類型",
            ["normal", "anomaly", "maintenance", "unknown"],
            format_func=lambda x: {
                "normal": "正常運作",
                "anomaly": "異常",
                "maintenance": "維護中",
                "unknown": "未知"
            }.get(x, x)
        )
        
        label_desc = st.text_input("描述 (選填)", placeholder="例如：冷卻水泵故障")
        
        if st.button("新增標籤", type="primary"):
            try:
                new_label = labeler.add_label(
                    str(label_start),
                    str(label_end),
                    label_type,
                    label_desc
                )
                st.success(f"標籤已新增！ID: {new_label['id']}")
            except Exception as e:
                st.error(f"新增標籤失敗: {e}")
        
        # Display existing labels
        st.markdown("### 現有標籤")
        existing_labels = labeler.get_labels()
        
        if existing_labels:
            labels_df = pd.DataFrame(existing_labels)
            labels_df['label_type'] = labels_df['label_type'].map({
                "normal": "正常運作",
                "anomaly": "異常",
                "maintenance": "維護中",
                "unknown": "未知"
            })
            st.dataframe(labels_df[['id', 'start_time', 'end_time', 'label_type', 'description']])
            
            # Delete label
            label_to_delete = st.selectbox(
                "選擇要刪除的標籤 ID",
                options=[l['id'] for l in existing_labels],
                key="delete_label"
            )
            if st.button("刪除標籤", type="secondary"):
                labeler.remove_label(label_to_delete)
                st.success("標籤已刪除")
                st.rerun()
        else:
            st.info("尚無標籤。請使用上方表單新增。")
    
    elif ml_section == "異常偵測":
        st.markdown("### 異常偵測 (Anomaly Detection)")
        st.info("使用 Isolation Forest 演算法自動偵測異常時段")
        
        contamination = st.slider(
            "異常比例 (Contamination)",
            min_value=0.01,
            max_value=0.20,
            value=0.05,
            step=0.01,
            help="預期資料中的異常比例，數值越高代表偵測到更多異常"
        )
        
        if st.button("執行異常偵測", type="primary"):
            with st.spinner("正在偵測異常..."):
                detector = AnomalyDetector(contamination=contamination)
                
                # 使用數值欄位進行偵測
                result_df = detector.fit_predict(filtered_df.copy())
                
                anomaly_count = result_df['is_anomaly'].sum()
                total_count = len(result_df)
                
                st.success(f"偵測完成！發現 {anomaly_count} 筆異常 ({anomaly_count/total_count*100:.1f}%)")
                
                # 儲存到 session state
                st.session_state['anomaly_result'] = result_df
                st.session_state['anomaly_periods'] = detector.get_anomaly_periods(result_df)
        
        # 顯示異常偵測結果
        if 'anomaly_result' in st.session_state:
            result_df = st.session_state['anomaly_result']
            
            # 視覺化異常
            if 'derived_Total_Power' in result_df.columns:
                fig = go.Figure()
                
                # 正常資料
                normal_df = result_df[~result_df['is_anomaly']]
                fig.add_trace(go.Scatter(
                    x=normal_df.index,
                    y=normal_df['derived_Total_Power'],
                    mode='lines',
                    name='正常',
                    line=dict(color='blue')
                ))
                
                # 異常資料
                anomaly_df = result_df[result_df['is_anomaly']]
                fig.add_trace(go.Scatter(
                    x=anomaly_df.index,
                    y=anomaly_df['derived_Total_Power'],
                    mode='markers',
                    name='異常',
                    marker=dict(color='red', size=8)
                ))
                
                fig.update_layout(title="異常偵測結果 - 總耗電量")
                st.plotly_chart(fig, use_container_width=True)
            
            # 顯示異常時段
            if 'anomaly_periods' in st.session_state:
                periods = st.session_state['anomaly_periods']
                if periods:
                    st.markdown("#### 異常時段列表")
                    for i, (start, end) in enumerate(periods[:10]):  # 最多顯示10個
                        st.write(f"{i+1}. {start} ~ {end}")
                    
                    if len(periods) > 10:
                        st.write(f"...還有 {len(periods)-10} 個時段")
    
    else:  # 能耗預測
        st.markdown("### 能耗預測 (Energy Prediction)")
        st.info("使用 Random Forest 模型預測能耗")
        
        if 'derived_Total_Power' not in filtered_df.columns:
            st.warning("此專案沒有總耗電量欄位，無法進行能耗預測")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("訓練模型", type="primary"):
                    with st.spinner("正在訓練模型..."):
                        predictor = EnergyPredictor()
                        
                        try:
                            score = predictor.train(filtered_df.copy(), target_col='derived_Total_Power')
                            
                            # 儲存到 session state
                            st.session_state['predictor'] = predictor
                            st.session_state['train_score'] = score
                            
                            st.success(f"模型訓練完成！R² 分數: {score:.4f}")
                            
                            # 顯示特徵重要性
                            importance = predictor.get_feature_importance()
                            if importance:
                                st.markdown("#### 特徵重要性 (Top 10)")
                                imp_df = pd.DataFrame(list(importance.items())[:10], columns=['特徵', '重要性'])
                                st.bar_chart(imp_df.set_index('特徵'))
                        except Exception as e:
                            st.error(f"訓練失敗: {e}")
            
            with col2:
                if st.button("執行預測", type="secondary"):
                    if 'predictor' not in st.session_state:
                        st.warning("請先訓練模型")
                    else:
                        with st.spinner("正在預測..."):
                            predictor = st.session_state['predictor']
                            pred_df = predictor.predict(filtered_df.copy())
                            st.session_state['pred_result'] = pred_df
                            st.success("預測完成！")
            
            # 顯示預測結果
            if 'pred_result' in st.session_state:
                pred_df = st.session_state['pred_result']
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=pred_df.index,
                    y=pred_df['derived_Total_Power'],
                    mode='lines',
                    name='實際值',
                    line=dict(color='blue')
                ))
                fig.add_trace(go.Scatter(
                    x=pred_df.index,
                    y=pred_df['predicted_power'],
                    mode='lines',
                    name='預測值',
                    line=dict(color='orange', dash='dash')
                ))
                
                fig.update_layout(title="實際 vs 預測能耗")
                st.plotly_chart(fig, use_container_width=True)
