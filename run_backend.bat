@echo off
cd /d "%~dp0"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
echo === QGuide backend ===  using %PY%
echo Installing backend dependencies (first run may take a minute)...
%PY% -m pip install -r requirements-api.txt
REM ---- local development settings (never use these values in production) ----
set "ENVIRONMENT=dev"
set "JWT_SECRET=local-demo-secret-not-for-production-use-1234"
set "ADMIN_EMAILS=hnreddy@biovaram.com"
set "QGUIDE_DEV_EMAIL=1"
set "EMAIL_BACKEND=console"
set "APP_BASE_URL=http://localhost:3000"
echo.
echo Starting API at http://localhost:8000   (docs at /docs)  -- press Ctrl+C to stop
%PY% -m uvicorn qguide.app.main:app --port 8000
pause
