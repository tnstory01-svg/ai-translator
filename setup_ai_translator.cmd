@echo off
setlocal
cd /d "%~dp0"

echo [AI Translator] Setup
echo.

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env file.
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create .venv. Check that Python is installed.
    pause
    exit /b 1
  )
)

echo Installing Python packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Package installation failed.
  pause
  exit /b 1
)

echo.
echo Setup complete.
echo Edit .env and put your API key before starting the app.
pause
