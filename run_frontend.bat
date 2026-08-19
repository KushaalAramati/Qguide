@echo off
cd /d "%~dp0web"
>.env.local echo NEXT_PUBLIC_API_URL=http://localhost:8000
if not exist "node_modules" (
  echo Installing frontend dependencies (first run, a few minutes)...
  call npm install
)
echo.
echo Starting UI at http://localhost:3000   -- press Ctrl+C to stop
call npm run dev
pause
