@echo off
title Diode Tester V5 - Installer
cls

:: Change to the directory where this script is located
cd /d "%~dp0"

:: Check if we're in the right place
if not exist "src" (
    echo ERROR: This installer must be run from the Diode Tester directory.
    echo Current directory: %CD%
    echo.
    echo Please navigate to the correct folder and try again.
    pause
    exit /b 1
)

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    cls
    echo ========================================
    echo         PYTHON NOT INSTALLED
    echo ========================================
    echo.
    echo Python is required to run Diode Tester V5.
    echo.
    echo Please install Python 3.8 or newer from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: During installation, make sure to:
    echo - Check "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: Run the console installer
python install_console.py

:: Keep window open if installer crashed
if errorlevel 1 (
    echo.
    echo Installer exited with an error.
    pause
)