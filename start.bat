@echo off
setlocal
cd /d "%~dp0"
title CRM NEW
if not exist "venv\Scripts\python.exe" (
  echo [1/3] Creating virtual environment...
  py -3 -m venv venv 2>nul || python -m venv venv
)
call "venv\Scripts\activate.bat"
python -c "import flask, flask_sqlalchemy" 2>nul
if errorlevel 1 (
  echo [2/3] Installing dependencies...
  python -m pip install --upgrade pip
  pip install -r requirements.txt
)
echo [3/3] Starting CRM NEW at http://localhost:5000
python run.py
pause
