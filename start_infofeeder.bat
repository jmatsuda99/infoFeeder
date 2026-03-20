@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Python virtual environment was not found at .venv\Scripts\python.exe
    pause
    exit /b 1
)

if not exist "app.py" (
    echo app.py was not found in %cd%
    pause
    exit /b 1
)

start "" ".venv\Scripts\python.exe" -m streamlit run app.py

endlocal
