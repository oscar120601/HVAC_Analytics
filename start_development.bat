@echo off
echo ============================================
echo  HVAC Analytics Development Server Starter
echo ============================================
echo.

:: Start Backend
echo [1/2] Starting FastAPI Backend...
echo.
start "Backend Server" cmd /k "cd /d "%~dp0backend" && call start_server.bat"

:: Wait for backend to start
timeout /t 3 /nobreak >nul

:: Start Frontend
echo [2/2] Starting React Frontend...
echo.
start "Frontend Server" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ============================================
echo  Both servers are starting!
echo.
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:3001
echo.
echo  Press any key to open browser...
echo ============================================
pause >nul

:: Open browser
start http://localhost:3001
