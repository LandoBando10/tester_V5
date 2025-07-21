@echo off
:: Diode Tester V5 - Professional Shortcut Creator
:: Creates desktop shortcuts without console window and security warnings

if "%1"=="silent" goto :silent_mode

echo ====================================================
echo     DIODE TESTER V5 - SHORTCUT CREATOR
echo ====================================================
echo.

:silent_mode
:: Detect desktop location
if exist "%USERPROFILE%\Desktop" (
    set "desktop=%USERPROFILE%\Desktop"
) else if exist "%USERPROFILE%\OneDrive\Desktop" (
    set "desktop=%USERPROFILE%\OneDrive\Desktop"
) else (
    if not "%1"=="silent" (
        echo ERROR: Could not find desktop location!
        pause
    )
    exit /b 1
)

:: Get the current directory (where the app is installed)
set "appdir=%~dp0"
:: Remove trailing backslash
set "appdir=%appdir:~0,-1%"

:: Check if pythonw.exe exists (for no console window)
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    set "python_exe=pythonw"
    set "python_console=python"
) else (
    :: Fallback to python.exe if pythonw not found
    set "python_exe=python"
    set "python_console=python"
    if not "%1"=="silent" (
        echo WARNING: pythonw.exe not found. Console window will be visible.
    )
)

:: Copy icon to local temp folder to avoid network drive issues
set "local_icon=%LOCALAPPDATA%\DiodeDynamics\shortcut_icon.ico"

:: Create local directory if it doesn't exist
if not exist "%LOCALAPPDATA%\DiodeDynamics" mkdir "%LOCALAPPDATA%\DiodeDynamics"

:: Check if icon exists and copy locally
if exist "%appdir%\resources\shortcut_icon.ico" (
    copy "%appdir%\resources\shortcut_icon.ico" "%local_icon%" >nul 2>&1
    if exist "%local_icon%" (
        set "icon_path=%local_icon%"
    ) else (
        :: If copy failed, try direct path
        set "icon_path=%appdir%\resources\shortcut_icon.ico"
    )
) else (
    :: Fallback to Python icon
    for /f "tokens=*" %%i in ('where python') do (
        set "python_path=%%i"
        goto :found_python
    )
    :found_python
    set "icon_path=%python_path%"
    if not "%1"=="silent" (
        echo WARNING: Custom icon not found. Using Python icon.
    )
)

:: Create the main shortcut (no console)
if not "%1"=="silent" echo Creating main shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$WshShell = New-Object -comObject WScript.Shell; ^
$Shortcut = $WshShell.CreateShortcut('%desktop%\Diode Tester.lnk'); ^
$Shortcut.TargetPath = '%python_exe%'; ^
$Shortcut.Arguments = '\"%appdir%\main.py\"'; ^
$Shortcut.WorkingDirectory = '%appdir%'; ^
$Shortcut.Description = 'Diode Dynamics Production Tester V5'; ^
$Shortcut.IconLocation = '%icon_path%, 0'; ^
$Shortcut.WindowStyle = 1; ^
$Shortcut.Save(); ^
Unblock-File -Path '%desktop%\Diode Tester V5.lnk' -ErrorAction SilentlyContinue"

:: Create debug shortcut (with console for troubleshooting)
if not "%1"=="silent" echo Creating debug shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$WshShell = New-Object -comObject WScript.Shell; ^
$Shortcut = $WshShell.CreateShortcut('%desktop%\Diode Tester (Debug).lnk'); ^
$Shortcut.TargetPath = '%python_console%'; ^
$Shortcut.Arguments = '\"%appdir%\main.py\"'; ^
$Shortcut.WorkingDirectory = '%appdir%'; ^
$Shortcut.Description = 'Diode Dynamics Production Tester V5 - Debug Mode'; ^
$Shortcut.IconLocation = '%icon_path%, 0'; ^
$Shortcut.WindowStyle = 1; ^
$Shortcut.Save(); ^
Unblock-File -Path '%desktop%\Diode Tester V5 (Debug).lnk' -ErrorAction SilentlyContinue"

:: Remove zone identifiers from Python files to reduce security warnings
if not "%1"=="silent" echo Removing security warnings from application files...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -Path '%appdir%' -Recurse -Include *.py,*.pyw,*.bat,*.ico -ErrorAction SilentlyContinue | ForEach-Object { Unblock-File -Path $_.FullName -ErrorAction SilentlyContinue }"

:: Verify shortcuts were created
set "success=1"
if not exist "%desktop%\Diode Tester.lnk" set "success=0"
if not exist "%desktop%\Diode Tester (Debug).lnk" set "success=0"

if "%success%"=="1" (
    if not "%1"=="silent" (
        echo.
        echo ====================================================
        echo SUCCESS: Shortcuts created successfully!
        echo ====================================================
        echo.
        echo Created shortcuts:
        echo - Diode Tester ^(Main application - no console^)
        echo - Diode Tester Debug ^(With console for troubleshooting^)
        echo.
        echo The shortcuts use:
        echo - No console window for normal operation
        echo - Custom icon when available
        echo - Reduced security warnings
        echo.
        pause
    )
    exit /b 0
) else (
    if not "%1"=="silent" (
        echo.
        echo ERROR: Could not create all shortcuts
        echo Please create shortcuts manually
        echo.
        pause
    )
    exit /b 1
)