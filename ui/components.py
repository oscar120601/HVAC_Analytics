"""
共用 UI 元件模組
包含圖表、表格、度量等可重用元件
"""

import streamlit as st
import polars as pl
import numpy as np
import pandas as pd
import plotly.figure_factory as ff
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Optional, Dict, Any


def get_analysis_numeric_cols(df: pl.DataFrame) -> List[str]:
    """
    獲取適合統計分析的數值欄位（排除 Date/Time/timestamp）
    
    Args:
        df: Polars DataFrame
        
    Returns:
        List[str]: 數值欄位名稱列表
    """
    exclude_cols = {'Date', 'Time', 'timestamp', 'date', 'time'}
    
    numeric_cols = [
        col for col in df.columns 
        if df[col].dtype in [pl.Float32, pl.Float64, pl.Int64, pl.Int32]
        and col not in exclude_cols
    ]
    return numeric_cols


def show_file_list(selected_files: List[str]):
    """顯示檔案清單預覽"""
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


def show_data_metrics(df: pl.DataFrame, prefix: str = ""):
    """
    顯示資料基本度量
    
    Args:
        df: Polars DataFrame
        prefix: 欄位前綴（用於 session state key）
    """
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("總列數", f"{len(df):,}")
    with col2:
        st.metric("總欄位數", f"{len(df.columns):,}")
    with col3:
        if 'timestamp' in df.columns:
            time_range = df['timestamp'].max() - df['timestamp'].min()
            st.metric("時間範圍", f"{time_range}")


def show_dataframe_preview(df: pl.DataFrame, title: str = "資料預覽", rows: int = 100):
    """顯示 DataFrame 預覽"""
    st.subheader(title)
    st.dataframe(
        df.head(rows).to_pandas(),
        use_container_width=True,
        height=400
    )


def show_column_list(df: pl.DataFrame, cols_per_row: int = 4):
    """以多列格式顯示欄位清單"""
    st.subheader("欄位清單")
    col_list = st.columns(cols_per_row)
    for i, col in enumerate(df.columns):
        with col_list[i % cols_per_row]:
            st.text(f"• {col}")


def show_correlation_heatmap(df: pl.DataFrame):
    """
    顯示相關性熱圖
    
    Args:
        df: Polars DataFrame
    """
    st.subheader("選擇變數進行相關性分析")
    
    numeric_cols = get_analysis_numeric_cols(df)
    
    if not numeric_cols:
        st.warning("沒有數值欄位可供分析")
        return
    
    # Let user select variables (max 15 for readability)
    max_vars = min(15, len(numeric_cols))
    selected_vars = st.multiselect(
        f"選擇要分析的變數（最多 {max_vars} 個，建議 5-10 個）",
        numeric_cols,
        default=numeric_cols[:min(8, len(numeric_cols))],
        max_selections=max_vars
    )
    
    if len(selected_vars) < 2:
        st.warning("請至少選擇 2 個變數進行相關性分析")
        return
    
    try:
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
            st.dataframe(pd.DataFrame(strong_corr), use_container_width=True)
        else:
            st.info("沒有發現強相關性（|r| > 0.7）的變數對")
    
    except Exception as e:
        st.error(f"計算相關性失敗: {str(e)}")
        st.exception(e)


def show_time_series(df: pl.DataFrame):
    """
    顯示時間序列圖表
    
    Args:
        df: Polars DataFrame（需包含 timestamp 欄位）
    """
    if 'timestamp' not in df.columns:
        st.error("資料中沒有 timestamp 欄位")
        return
    
    numeric_cols = get_analysis_numeric_cols(df)
    
    if not numeric_cols:
        st.warning("沒有數值欄位可供分析")
        return
    
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


def show_distribution(df: pl.DataFrame, selected_col: str):
    """
    顯示單一欄位的分布圖
    
    Args:
        df: Polars DataFrame
        selected_col: 要分析的欄位名稱
    """
    col_data = df[selected_col]
    col_data_clean = col_data.drop_nulls()
    
    # Show metrics
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
    
    pandas_data = col_data_clean.to_pandas()
    
    if len(pandas_data) > 0:
        # Create histogram using numpy
        counts, bin_edges = np.histogram(pandas_data, bins=30)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
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


def show_quality_dashboard(df: pl.DataFrame):
    """
    顯示資料品質儀表板
    
    Args:
        df: Polars DataFrame
    """
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
    
    exclude_missing_cols = {'Date', 'Time', 'timestamp', 'date', 'time'}
    
    missing_data = []
    for col in df.columns:
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
        missing_df = pd.DataFrame(missing_data).sort_values('缺失數量', ascending=False)
        st.dataframe(missing_df, use_container_width=True)
        
        # Visualize missing data
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


def show_physics_validation_status(df: pl.DataFrame):
    """
    顯示物理驗證狀態
    
    Args:
        df: Polars DataFrame
    """
    st.subheader("🔬 物理驗證狀態")
    
    validation_cols = st.columns(3)
    
    with validation_cols[0]:
        st.markdown("**📊 穩態檢測**")
        if 'is_steady_state' in df.columns:
            steady_count = df['is_steady_state'].sum()
            total_count = len(df)
            steady_pct = (steady_count / total_count * 100) if total_count > 0 else 0
            st.metric("穩態資料", f"{steady_count:,} ({steady_pct:.1f}%)")
            
            steady_data = {'狀態': ['穩態', '非穩態'], '數量': [steady_count, total_count - steady_count]}
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
            
            if 'affinity_ratio' in df.columns:
                ratio_data = df['affinity_ratio'].drop_nulls()
                if len(ratio_data) > 0:
                    st.caption(f"比率範圍: {ratio_data.min():.4f} ~ {ratio_data.max():.4f}")
        else:
            st.caption("未執行親和力定律檢查")


def show_frozen_data_detection(df: pl.DataFrame):
    """顯示凍結資料偵測結果"""
    st.subheader("❄️ 凍結資料偵測")
    
    frozen_cols = [col for col in df.columns if '_frozen' in col]
    
    if frozen_cols:
        frozen_summary = []
        for col in frozen_cols:
            original_col = col.replace('_frozen', '')
            frozen_count = df[col].sum()
            if frozen_count > 0:
                frozen_pct = (frozen_count / len(df)) * 100
                frozen_summary.append({
                    '感測器': original_col,
                    '凍結點數': frozen_count,
                    '凍結比例': f"{frozen_pct:.2f}%",
                    '狀態': '🔴 警告' if frozen_pct > 5 else '🟡 注意'
                })
        
        if frozen_summary:
            frozen_df = pd.DataFrame(frozen_summary).sort_values('凍結點數', ascending=False)
            st.dataframe(frozen_df, use_container_width=True)
            st.warning("⚠️ 凍結資料可能表示感測器故障或數據傳輸問題")
        else:
            st.success("✅ 沒有偵測到凍結資料")
    else:
        st.info("資料中無凍結標記欄位")


def calculate_quality_score(df: pl.DataFrame) -> float:
    """
    計算資料品質評分（0-100）
    
    Args:
        df: Polars DataFrame
        
    Returns:
        float: 品質評分
    """
    quality_score = 100
    total_rows = len(df)
    
    # Calculate missing data penalty
    exclude_missing_cols = {'Date', 'Time', 'timestamp', 'date', 'time'}
    missing_count = sum(1 for col in df.columns if col not in exclude_missing_cols and df[col].null_count() > 0)
    
    if missing_count > 0:
        avg_missing_pct = sum(df[col].null_count() / total_rows * 100 for col in df.columns if col not in exclude_missing_cols) / len(df.columns)
        quality_score -= min(avg_missing_pct, 30)
    
    # Deduct points for frozen data
    frozen_cols = [col for col in df.columns if '_frozen' in col]
    if frozen_cols:
        frozen_count = sum([df[col].sum() for col in frozen_cols])
        frozen_pct = (frozen_count / (total_rows * len(frozen_cols))) * 100 if frozen_cols else 0
        quality_score -= min(frozen_pct, 20)
    
    return max(0, quality_score)


def show_quality_score(quality_score: float):
    """顯示品質評分和建議"""
    st.subheader("⭐ 整體品質評分")
    
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
        st.progress(quality_score / 100)
    
    # Recommendations
    if quality_score < 90:
        st.markdown("---")
        st.subheader("💡 改善建議")
        st.markdown("- 檢查缺失比例 > 10% 的欄位，考慮補值或移除")
        st.markdown("- 檢查凍結資料的感測器，可能需要維護")
        st.markdown("- 確認資料收集頻率與預期一致")
        st.markdown("- 考慮進行異常值偵測與處理")


def show_export_buttons(df: pl.DataFrame, filename_prefix: str = "hvac_etl_output"):
    """
    顯示匯出按鈕
    
    Args:
        df: Polars DataFrame
        filename_prefix: 檔名前綴
    """
    from datetime import datetime
    from io import BytesIO
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV export
        csv_data = df.write_csv()
        st.download_button(
            label="📥 下載 CSV",
            data=csv_data,
            file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Parquet export
        buffer = BytesIO()
        df.write_parquet(buffer)
        parquet_data = buffer.getvalue()
        
        st.download_button(
            label="📥 下載 Parquet",
            data=parquet_data,
            file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet",
            mime="application/octet-stream"
        )
    
    st.info("💡 Parquet 格式較小且效能更好，適合大型資料集")
