import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from data_parser import merge_datasets
from data_pipeline import run_pipeline

st.set_page_config(page_title="HVAC Analytics", layout="wide")

@st.cache_data
def load_data():
    DATA_DIR = os.path.join("data", "Farglory_O3")
    df = merge_datasets(DATA_DIR)
    if df is not None:
        df = run_pipeline(df)
    return df

st.title("HVAC Data Cleaning & Visualization Dashboard")

# Load Data
with st.spinner('Loading and processing data...'):
    df = load_data()

if df is None or df.empty:
    st.error("No data found or failed to parse. Please check 'data/Farglory_O3' folder.")
    st.stop()

# Sidebar: Filters
st.sidebar.header("Filters")
min_date = df.index.min().date()
max_date = df.index.max().date()

start_date = st.sidebar.date_input("Start Date", min_date)
end_date = st.sidebar.date_input("End Date", max_date)

# Filter data
mask = (df.index.date >= start_date) & (df.index.date <= end_date)
filtered_df = df.loc[mask]

st.sidebar.markdown("---")
st.sidebar.info(f"Data Range: {min_date} to {max_date}")
st.sidebar.info(f"Records: {len(filtered_df)}")

# Tabs
tab1, tab2, tab3 = st.tabs(["Trends Analysis", "Correlation Analysis", "Raw Data"])

with tab1:
    st.subheader("Time Series Trends")
    
    # 1. Environmental Conditions
    st.markdown("### 1. Environmental Conditions")
    env_cols = [c for c in df.columns if 'OAT' in c or 'OAH' in c or 'WetBulb' in c]
    if env_cols:
        fig_env = px.line(filtered_df, y=env_cols, title="Outer Air Temp / Humidity / Wet Bulb")
        st.plotly_chart(fig_env, use_container_width=True)
    
    # 2. Power Consumption
    st.markdown("### 2. Power Consumption")
    pwr_col = 'derived_Total_Power'
    if pwr_col in filtered_df.columns:
        fig_pwr = px.line(filtered_df, y=pwr_col, title="Total Power Consumption (kWh)")
        st.plotly_chart(fig_pwr, use_container_width=True)
    else:
        st.warning("Total Power column not found.")

    # 3. AHU Details
    st.markdown("### 3. AHU Performance")
    # Identify AHUs
    ahu_cols = [c for c in df.columns if '.CV' in c or '.SAT' in c]
    ahus = sorted(list(set([c.split('.')[0] for c in ahu_cols]))) # Extract 'AH01-1', etc.
    
    selected_ahu = st.selectbox("Select AHU", ahus)
    
    if selected_ahu:
        ahu_vars = [c for c in df.columns if c.startswith(selected_ahu)]
        if ahu_vars:
            fig_ahu = go.Figure()
            for var in ahu_vars:
                # Plot different scales? 
                # CV is %, Temp is C.
                if '.CV' in var:
                    fig_ahu.add_trace(go.Scatter(x=filtered_df.index, y=filtered_df[var], name=var + " (%)", yaxis='y2'))
                else:
                    fig_ahu.add_trace(go.Scatter(x=filtered_df.index, y=filtered_df[var], name=var + " (C)"))
            
            fig_ahu.update_layout(
                title=f"{selected_ahu} Trends",
                yaxis=dict(title="Temperature (C)"),
                yaxis2=dict(title="Valve Opening (%)", overlaying='y', side='right', range=[0, 100])
            )
            st.plotly_chart(fig_ahu, use_container_width=True)

with tab2:
    st.subheader("Correlation Analysis")
    
    # Scatter: OAT vs Total Power
    if 'derived_Total_Power' in df.columns:
        oat_col = [c for c in df.columns if 'OAT' in c][0] if [c for c in df.columns if 'OAT' in c] else None
        
        if oat_col:
            st.markdown("#### Power vs. Outer Air Temp")
            fig_corr = px.scatter(filtered_df, x=oat_col, y='derived_Total_Power', 
                                color=filtered_df.index.hour, 
                                title=f"Correlation: {oat_col} vs Total Power",
                                labels={'color': 'Hour of Day'})
            st.plotly_chart(fig_corr, use_container_width=True)
            
    # Scatter: Flow vs Power (Placeholder)
    st.markdown("#### Flow vs. Power (Placeholder)")
    flow_cols = [c for c in df.columns if 'LPM' in c or 'GPM' in c or 'Flow' in c]
    if flow_cols and 'derived_Total_Power' in df.columns:
        fig_flow = px.scatter(filtered_df, x=flow_cols[0], y='derived_Total_Power',
                              title="Flow vs Power")
        st.plotly_chart(fig_flow, use_container_width=True)
    else:
        st.info("Flow meter data not detected or Power data missing.")

with tab3:
    st.subheader("Data Inspector")
    st.dataframe(filtered_df.head(100))
    st.markdown("### Missing Data Heatmap")
    # Quick check for missing entries in visible window
    st.write(filtered_df.isnull().sum())
