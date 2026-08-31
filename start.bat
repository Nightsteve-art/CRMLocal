@echo off
setlocal
cd /d "%~dp0"

echo Starting Eko-Production CRM from:
echo %CD%

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv venv 2>nul || python -m venv venv
)

call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

python -c "import flask, flask_sqlalchemy, pandas" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
)

python app.py
pause
