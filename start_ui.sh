#!/bin/bash
# Quick start script for HVAC ETL UI

echo "🏭 啟動 HVAC ETL 測試介面..."
echo ""
echo "介面將在瀏覽器開啟: http://localhost:8501"
echo ""
echo "按 Ctrl+C 停止伺服器"
echo ""

cd "$(dirname "$0")"
python3 -m streamlit run etl_ui.py
