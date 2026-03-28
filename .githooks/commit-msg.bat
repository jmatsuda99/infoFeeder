@echo off
setlocal
set REPO_ROOT=%~dp0..
set PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe
if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" "%REPO_ROOT%\bump_version.py" "%~1"
) else (
  python "%REPO_ROOT%\bump_version.py" "%~1"
)
if errorlevel 1 exit /b 1
git -C "%REPO_ROOT%" add VERSION
exit /b %errorlevel%
