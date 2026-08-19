@echo off
cd /d "%~dp0"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
echo === QGuide backend ===  using %PY%
echo Installing backend dependencies (first run may take a minute)...
%PY% -m pip install -r requirements-api.txt
set "JWT_SECRET=local-demo-secret"
set "ADMIN_EMAILS=hnreddy@biovaram.com"
echo.
echo Starting API at http://localhost:8000   (docs at /docs)  -- press Ctrl+C to stop
%PY% -m uvicorn qguide.app.main:app --port 8000
pause
