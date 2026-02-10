@echo off
chcp 65001 >nul
echo ========================================
echo HVAC Analytics - Streamlit UI 重啟工具
echo ========================================
echo.

echo [1/3] 正在終止現有的 Streamlit 進程...
taskkill /F /IM python.exe /FI "COMMANDLINE eq *streamlit*" 2>nul
if %errorlevel% == 0 (
    echo ✓ 已終止現有進程
) else (
    echo ℹ 沒有運行中的 Streamlit 進程
)

echo.
echo [2/3] 清除快取...
if exist "__pycache__" rd /s /q "__pycache__" 2>nul
if exist "src\__pycache__" rd /s /q "src\__pycache__" 2>nul
if exist "src\config\__pycache__" rd /s /q "src\config\__pycache__" 2>nul
if exist "src\etl\__pycache__" rd /s /q "src\etl\__pycache__" 2>nul
if exist "src\models\__pycache__" rd /s /q "src\models\__pycache__" 2>nul
if exist "src\optimization\__pycache__" rd /s /q "src\optimization\__pycache__" 2>nul
echo ✓ 快取已清除

echo.
echo [3/3] 啟動 Streamlit UI...
echo ========================================
python -m streamlit run etl_ui.py

echo.
pause
