@echo off
echo ============================================
echo  HVAC Analytics Backend Server
echo ============================================
echo.

:: Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate
) else (
    echo Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate
    
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo Starting FastAPI Server...
echo.
echo Server will be available at:
echo   - http://localhost:8000
echo   - API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop
echo ============================================

python main.py
