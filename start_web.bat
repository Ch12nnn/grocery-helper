@echo off
chcp 65001 >nul
title Shanghai Grocery Companion
cd /d "%~dp0"

set "PYTHON_EXEC=python"
if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_EXEC=%~dp0venv\Scripts\python.exe"
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXEC=%~dp0.venv\Scripts\python.exe"

echo ========================================================
echo   Shanghai Grocery Web Server
echo ========================================================
echo.
echo Starting Web Server on http://localhost:5000 ...
echo Python: %PYTHON_EXEC%
echo.

start "" "http://localhost:5000"

"%PYTHON_EXEC%" "%~dp0web_app.py" 5000

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Server stopped with error code %ERRORLEVEL%
    pause
)
