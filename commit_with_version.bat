@echo off
setlocal

if "%~1"=="" (
  echo Usage: commit_with_version.bat ^<commit message^>
  exit /b 1
)

set REPO_ROOT=%~dp0
set PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe

if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" "%REPO_ROOT%\commit_with_version.py" %*
) else (
  python "%REPO_ROOT%\commit_with_version.py" %*
)

exit /b %errorlevel%
