@echo off
title Diode Tester V5 - Professional Installer
color 0B
cls

echo.
echo    ====================================================
echo            DIODE DYNAMICS - PRODUCTION TESTER V5           
echo                   PROFESSIONAL INSTALLER                   
echo    ====================================================
echo.
echo    This installer will:
echo    - Check Python installation
echo    - Install required packages  
echo    - Create a desktop shortcut
echo.
echo    Press any key to begin installation...
pause >nul

:: Check if Python is installed
cls
echo.
echo    Checking system requirements...
echo.
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo.
    echo    [ERROR] Python is not installed!
    echo.
    echo    Please install Python 3.8 or newer from:
    echo    https://www.python.org/downloads/
    echo.
    echo    IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    echo    Press any key to exit...
    pause >nul
    exit /b 1
)

:: Check if we can use the GUI installer
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    :: PySide6 not installed, use basic installer
    echo    Python found. Installing packages...
    echo.
    call "%~dp0install_for_users.bat"
) else (
    :: PySide6 available, use GUI installer
    cls
    echo.
    echo    Launching graphical installer...
    echo.
    python "%~dp0install_with_gui.py"
)

exit /b %errorlevel%