@echo off
REM ---- QGuide: start the whole app (API + web) in two windows ----
REM Double-click this file. Two console windows open:
REM   [1] backend  -> http://localhost:8000  (API, docs at /docs)
REM   [2] web      -> http://localhost:3000  (open this one in your browser)
REM Close either window (or Ctrl+C in it) to stop that half.
cd /d "%~dp0"
start "QGuide backend (API :8000)" cmd /k run_backend.bat
timeout /t 4 /nobreak >nul
start "QGuide web (UI :3000)" cmd /k run_frontend.bat
echo Both halves are starting in their own windows. Open http://localhost:3000 once the web window says "Ready".
timeout /t 8 >nul
