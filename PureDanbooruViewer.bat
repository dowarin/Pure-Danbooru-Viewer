@echo off
setlocal enabledelayedexpansion

:: Check if Python is installed
python --version > nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Please install Python first.
    pause
    exit /b
)

:: Install required packages
echo Installing required packages...
python -m pip install -r requirements.txt

:: Change to script directory
cd /d "%~dp0"

:: Run main script
echo Starting Pure-Danbooru Viewer...
python PureDanbooruViewer.py
if errorlevel 1 (
    echo An error occurred while running the application.
    pause
)
exit /b