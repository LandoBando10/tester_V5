@echo off
echo ========================================
echo Testing Shortcut Creation
echo ========================================
echo.

:: Test if pythonw exists
echo Checking for pythonw.exe...
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] pythonw.exe found - Console window will be hidden
) else (
    echo [WARNING] pythonw.exe not found - Console window will be visible
)

:: Test if icon exists
echo.
echo Checking for icon file...
if exist "resources\shortcut_icon.ico" (
    echo [OK] Icon file found at resources\shortcut_icon.ico
) else (
    echo [WARNING] Icon file not found - Will use Python icon
)

:: Test Python availability
echo.
echo Checking Python installation...
python --version
if %errorlevel% equ 0 (
    echo [OK] Python is available
) else (
    echo [ERROR] Python not found in PATH
)

echo.
echo ========================================
echo Ready to create shortcuts?
echo ========================================
echo.
pause

:: Run the shortcut creator
call create_shortcuts.bat

echo.
echo Test complete!
pause