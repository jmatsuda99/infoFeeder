@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Python virtual environment was not found at .venv\Scripts\python.exe
    pause
    exit /b 1
)

if not exist "launcher.py" (
    echo launcher.py was not found in %cd%
    pause
    exit /b 1
)

"%~dp0.venv\Scripts\python.exe" "%~dp0launcher.py" open

endlocal
