@echo off
title Diode Tester V5 - Installation
color 0A
echo ========================================
echo   DIODE TESTER V5 - INSTALLATION
echo ========================================
echo.

:: Check if Python is installed
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo.
    echo ERROR: Python is not installed!
    echo.
    echo Please install Python 3.8 or newer from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

:: Display Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo Found Python %PYTHON_VER%
echo.

:: Install requirements
echo [2/4] Installing required packages...
echo This may take a few minutes...
echo.

:: Core requirements
echo Installing PySide6 (GUI framework)...
python -m pip install --upgrade PySide6 --quiet --disable-pip-version-check
if errorlevel 1 goto :install_error

echo Installing pyserial (Arduino communication)...
python -m pip install --upgrade pyserial --quiet --disable-pip-version-check
if errorlevel 1 goto :install_error

echo Installing numpy (Data processing)...
python -m pip install --upgrade numpy --quiet --disable-pip-version-check
if errorlevel 1 goto :install_error

echo Installing packaging (Version management)...
python -m pip install --upgrade packaging --quiet --disable-pip-version-check
if errorlevel 1 goto :install_error

:: Optional but recommended
echo Installing pyqtgraph (Live graphs - optional)...
python -m pip install --upgrade pyqtgraph --quiet --disable-pip-version-check 2>nul

echo.
echo [3/4] All packages installed successfully!
echo.

:: Create desktop shortcut
echo [4/4] Creating desktop shortcut...
call "%~dp0create_professional_shortcut.bat" silent

echo.
color 0A
echo ========================================
echo   INSTALLATION COMPLETE!
echo ========================================
echo.
echo Diode Tester V5 has been installed successfully!
echo.
echo A shortcut has been created on your desktop.
echo Double-click "Diode Tester V5" to start the application.
echo.
echo Press any key to exit...
pause >nul
exit /b 0

:install_error
color 0C
echo.
echo ERROR: Package installation failed!
echo.
echo Please check your internet connection and try again.
echo If the problem persists, contact IT support.
echo.
pause
exit /b 1