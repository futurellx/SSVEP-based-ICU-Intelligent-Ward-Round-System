@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=%USERPROFILE%\.conda\envs\ICUenv\python.exe"
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Python environment was not found. See PYCHARM_SETUP.md.
  pause
  exit /b 1
)
set "PYTHONUNBUFFERED=1"
set "PYTHONNOUSERSITE=1"
set "PYTHONIOENCODING=utf-8"
"%PYTHON%" "%~dp0start_controller.py"
if errorlevel 1 pause
endlocal
