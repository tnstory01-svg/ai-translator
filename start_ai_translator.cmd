@echo off
setlocal
cd /d "%~dp0"

if not exist ".env" (
  copy ".env.example" ".env" >nul
)

if not exist ".venv\Scripts\python.exe" (
  echo Python environment is not ready.
  echo Run setup_ai_translator.cmd first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -c "import anthropic, fastapi, httpx, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo Required packages are not installed.
  echo Run setup_ai_translator.cmd first.
  pause
  exit /b 1
)

start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"

echo [AI Translator]
echo Running at http://127.0.0.1:8000
echo Keep this window open while using the app.
echo Press Ctrl+C to stop.
echo.

".venv\Scripts\python.exe" -m uvicorn web_app:app --host 127.0.0.1 --port 8000
pause
