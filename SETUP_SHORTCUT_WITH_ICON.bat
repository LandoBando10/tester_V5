@echo off
echo ===============================================
echo Diode Tester V5 - Desktop Shortcut Setup
echo ===============================================
echo.

REM Check if Python is available
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH!
    echo Please install Python first.
    pause
    exit /b 1
)

REM Check if shortcut_icon.ico already exists
if not exist "resources\shortcut_icon.ico" (
    echo Converting logo to icon format...
    python convert_icon.py
    if %errorlevel% neq 0 (
        echo.
        echo WARNING: Could not convert icon. Continuing without custom icon.
        echo You may need to install Pillow: pip install Pillow
        echo.
    ) else (
        echo Icon converted successfully!
    )
) else (
    echo Icon file already exists.
)

echo.
echo Creating desktop shortcut...
cscript //NoLogo CreateShortcut.vbs

echo.
echo ===============================================
echo Setup complete!
echo ===============================================
echo.
echo The shortcut "Diode Tester V5" has been created on your desktop.
echo The program will run without showing a console window.
echo.
pause