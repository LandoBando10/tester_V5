@echo off
title Diode Tester V5 - Professional Installer (DEBUG)
color 0B
cls

echo.
echo    ====================================================
echo            DIODE DYNAMICS - PRODUCTION TESTER V5           
echo                   PROFESSIONAL INSTALLER                   
echo    ====================================================
echo.
echo    DEBUG MODE - Will show all errors
echo.
echo    Press any key to begin installation...
pause >nul

:: Check if Python is installed
cls
echo.
echo    [1/3] Checking Python installation...
echo.
python --version
if errorlevel 1 (
    color 0C
    echo.
    echo    [ERROR] Python is not installed or not in PATH!
    echo.
    echo    Please install Python 3.8 or newer from:
    echo    https://www.python.org/downloads/
    echo.
    echo    IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

:: Check current directory
echo.
echo    [2/3] Current directory:
echo    %CD%
echo.
echo    Files in current directory:
dir /b *.py *.bat
echo.

:: Check if we can use the GUI installer
echo    [3/3] Checking for PySide6...
python -c "import PySide6; print('PySide6 version:', PySide6.__version__)"
if errorlevel 1 (
    :: PySide6 not installed
    echo.
    echo    PySide6 not found. Installing required packages...
    echo.
    
    :: Install PySide6 first
    echo    Installing PySide6...
    python -m pip install PySide6
    if errorlevel 1 (
        echo.
        echo    ERROR: Failed to install PySide6
        pause
        exit /b 1
    )
)

:: Try to run GUI installer with full error output
echo.
echo    Launching graphical installer...
echo    (If this fails, error will be shown below)
echo.

:: Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Check if install_with_gui.py exists
if not exist "install_with_gui.py" (
    echo    ERROR: install_with_gui.py not found!
    echo    Looking in: %CD%
    echo.
    echo    Available Python files:
    dir /b *.py
    pause
    exit /b 1
)

:: Run with full output
python install_with_gui.py
if errorlevel 1 (
    echo.
    echo    ERROR: GUI installer failed with error code %errorlevel%
    echo.
    echo    Trying to get more info...
    python -c "import traceback; import install_with_gui; install_with_gui.main()" 2>&1
)

echo.
echo    Installation process completed.
echo.
pause
exit /b %errorlevel%