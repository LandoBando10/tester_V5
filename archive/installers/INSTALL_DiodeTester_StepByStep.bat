@echo off
title Diode Tester V5 - Step by Step Installer
color 0B
cls

echo.
echo    ====================================================
echo            DIODE DYNAMICS - PRODUCTION TESTER V5           
echo                   STEP BY STEP INSTALLER                   
echo    ====================================================
echo.
echo    This will pause at each step so we can see what happens.
echo.
pause

:: Step 1: Check Python
cls
echo STEP 1: Checking if Python is installed...
echo.
where python
echo.
python --version
echo.
echo Exit code: %errorlevel%
echo.
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)
echo Python found successfully!
pause

:: Step 2: Check current directory and files
cls
echo STEP 2: Checking current directory...
echo.
echo Current directory: %CD%
echo.
echo Files in this directory:
dir /b
echo.
echo Looking for install_with_gui.py...
if exist "install_with_gui.py" (
    echo FOUND: install_with_gui.py
) else (
    echo ERROR: install_with_gui.py NOT FOUND!
)
echo.
echo Looking for src directory...
if exist "src" (
    echo FOUND: src directory
    echo Contents of src:
    dir /b src
) else (
    echo ERROR: src directory NOT FOUND!
)
echo.
pause

:: Step 3: Test Python imports
cls
echo STEP 3: Testing Python can import PySide6...
echo.
python -c "import PySide6; print('PySide6 imported successfully')"
echo Exit code: %errorlevel%
echo.
if errorlevel 1 (
    echo PySide6 not installed. Need to install it first...
    echo Running: python -m pip install PySide6
    python -m pip install PySide6
    echo.
    echo Installation exit code: %errorlevel%
)
pause

:: Step 4: Test if we can import the project modules
cls
echo STEP 4: Testing if Python can find our project modules...
echo.
echo Testing basic import...
python -c "import sys; sys.path.insert(0, '.'); from src.gui.startup import UnifiedSplashScreen; print('Success: Can import UnifiedSplashScreen')"
echo Exit code: %errorlevel%
echo.
if errorlevel 1 (
    echo ERROR: Cannot import project modules!
    echo.
    echo Python path test:
    python -c "import sys; print('Python paths:'); [print(p) for p in sys.path]"
)
pause

:: Step 5: Try to run the installer
cls
echo STEP 5: Attempting to run install_with_gui.py...
echo.
echo Running: python install_with_gui.py
echo.
python install_with_gui.py
echo.
echo Exit code: %errorlevel%
echo.
if errorlevel 1 (
    echo ERROR: Installer failed!
    echo.
    echo Trying with more debug info:
    python -u install_with_gui.py 2>&1
)
echo.
pause

:: If we get here, something worked
echo.
echo Process completed. Check above for any errors.
echo.
pause