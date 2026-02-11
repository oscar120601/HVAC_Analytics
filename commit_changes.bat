@echo off
echo ============================================
echo  HVAC Analytics - Git Commit Helper
echo ============================================
echo.

REM Remove lock file if exists
if exist ".git\index.lock" (
    echo Removing git lock file...
    del /f ".git\index.lock" 2>nul
    timeout /t 1 /nobreak >nul
)

echo Adding files to git...

git add .gitignore
git add BACKEND_INTEGRATION_SUMMARY.md
git add DEVELOPMENT_SETUP.md
git add FRONTEND_MIGRATION_GUIDE.md
git add COMMIT_PENDING.md
git add commit_changes.bat

REM Add backend files (excluding .venv)
git add backend/main.py
git add backend/requirements.txt
git add backend/start_server.bat
git add backend/test_api.py
git add backend/README.md

REM Add frontend source files
git add frontend/.env
git add frontend/package.json
git add frontend/tsconfig*.json
git add frontend/vite.config.ts
git add frontend/index.html
git add frontend/tailwind.config.js
git add frontend/eslint.config.js
git add frontend/components.json
git add frontend/src/

REM Add root files
git add start_development.bat

echo.
echo Files staged. Ready to commit!
echo.
echo Run the following command to commit:
echo   git commit -m "feat: Add FastAPI backend and React frontend integration"
echo.
echo Or run with detailed message:
echo   git commit -m "feat: Add FastAPI backend and React frontend integration" -m "- Add FastAPI backend with 9 API endpoints" -m "- Create API client and React hooks" -m "- Add ConnectionStatus component" -m "- Add development setup documentation"
echo.

pause
