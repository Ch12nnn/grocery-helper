@echo off
chcp 65001 >nul
title Shanghai Grocery Data Sync
cd /d "%~dp0"

set "PYTHON_EXEC=python"
if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_EXEC=%~dp0venv\Scripts\python.exe"
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXEC=%~dp0.venv\Scripts\python.exe"

"%PYTHON_EXEC%" "%~dp0main.py" %*

if %ERRORLEVEL% NEQ 0 (
    echo Error occurred with code %ERRORLEVEL%
    pause
)
