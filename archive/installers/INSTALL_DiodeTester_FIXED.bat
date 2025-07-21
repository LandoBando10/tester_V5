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
pause

:: CRITICAL: Change to the root directory where src/ is located
echo.
echo [STEP 1] Navigating to application root...
cd /d "%~dp0"
if exist "deployment" (
    :: We're in the root already
    echo Already in root directory
) else if exist "..\src" (
    :: We're in a subdirectory, go up
    cd ..
    echo Moved to root directory
) else if exist "..\..\src" (
    :: We're two levels deep
    cd ..\..
    echo Moved to root directory
)
echo Current directory: %CD%
echo.
pause

:: Verify we're in the right place
echo [STEP 2] Verifying installation files...
echo.
if not exist "src" (
    echo ERROR: Cannot find src directory!
    echo Current directory: %CD%
    echo.
    echo Contents of current directory:
    dir /b
    pause
    exit /b 1
) else (
    echo FOUND: src directory
)

if not exist "install_with_gui.py" (
    echo ERROR: Cannot find install_with_gui.py!
    echo Current directory: %CD%
    echo.
    echo Python files in current directory:
    dir /b *.py
    pause
    exit /b 1
) else (
    echo FOUND: install_with_gui.py
)
echo.
pause

:: Check if Python is installed
echo [STEP 3] Checking Python installation...
echo.
python --version
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
    pause
    exit /b 1
)
echo Python installation verified!
echo.
pause

:: Check if we can use the GUI installer
echo [STEP 4] Checking for required packages...
echo.
python -c "import PySide6; print('PySide6 is already installed')"
if errorlevel 1 (
    :: PySide6 not installed, install it first
    echo PySide6 not found. Installing required packages...
    echo.
    echo This may take a few minutes on first install...
    echo.
    echo Installing: PySide6 pyserial numpy packaging
    python -m pip install PySide6 pyserial numpy packaging
    if errorlevel 1 (
        echo.
        echo    ERROR: Failed to install packages.
        echo    Please check your internet connection.
        pause
        exit /b 1
    )
    echo.
    echo Package installation complete!
)
echo.
pause

:: Run GUI installer
echo [STEP 5] Launching graphical installer...
echo.
echo Current directory: %CD%
echo Running: python install_with_gui.py
echo.
python install_with_gui.py

if errorlevel 1 (
    echo.
    echo ERROR: Installation failed with exit code %errorlevel%
    echo.
    echo Trying with more details:
    python -u install_with_gui.py 2>&1
    echo.
    pause
)

echo.
echo Installation process completed.
echo.
pause
exit /b %errorlevel%