@echo off
REM ---- Q-Guide launcher ----
REM Double-click this file (or run it from a terminal) to start the app.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Q-Guide] Python venv not found at .venv\Scripts\python.exe
    echo Create it with:  py -3.12 -m venv .venv  ^&^&  .venv\Scripts\python -m pip install -r qguide\requirements.txt
    pause
    exit /b 1
)

echo [Q-Guide] Starting on http://localhost:8501  (Ctrl+C to stop)
".venv\Scripts\python.exe" -m streamlit run qguide\frontend\streamlit_app.py --server.port=8501 --server.address=0.0.0.0
pause
