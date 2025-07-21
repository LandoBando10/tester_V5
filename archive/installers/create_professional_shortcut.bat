@echo off
if "%1"=="silent" goto :silent_mode

echo Creating professional desktop shortcut for Diode Tester V5...
echo.

:silent_mode
:: Detect desktop location
if exist "%USERPROFILE%\Desktop" (
    set "desktop=%USERPROFILE%\Desktop"
) else if exist "%USERPROFILE%\OneDrive\Desktop" (
    set "desktop=%USERPROFILE%\OneDrive\Desktop"
) else (
    if not "%1"=="silent" (
        echo ERROR: Could not find desktop!
        pause
    )
    exit /b 1
)

:: Get the current directory (shared drive location)
set "appdir=%~dp0"

:: Create a launcher batch file with nice window
(
echo @echo off
echo title Diode Dynamics - Production Tester V5
echo color 0F
echo cls
echo.
echo echo Starting Diode Tester V5...
echo cd /d "%appdir%"
echo.
echo :: Check if Python is available
echo python --version ^>nul 2^>^&1
echo if errorlevel 1 ^(
echo     color 0C
echo     echo ERROR: Python is not installed or not in PATH!
echo     echo.
echo     echo Please install Python or contact IT support.
echo     echo.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo :: Launch the application
echo python main.py --shared-drive "B:\Users\Landon Epperson\Tester"
echo.
echo :: If app crashes, keep window open
echo if errorlevel 1 ^(
echo     echo.
echo     echo Application exited with an error.
echo     pause
echo ^)
) > "%appdir%DiodeTesterLauncher.bat"

:: Create the shortcut using PowerShell
powershell -NoProfile -Command ^
"$WshShell = New-Object -comObject WScript.Shell; ^
$Shortcut = $WshShell.CreateShortcut('%desktop%\Diode Tester V5.lnk'); ^
$Shortcut.TargetPath = '%appdir%DiodeTesterLauncher.bat'; ^
$Shortcut.WorkingDirectory = '%appdir%'; ^
$Shortcut.Description = 'Diode Dynamics Production Tester V5 - Professional Testing Software'; ^
$Shortcut.IconLocation = '%appdir%resources\shortcut_icon.ico, 0'; ^
$Shortcut.WindowStyle = 7; ^
$Shortcut.Save()"

:: Verify shortcut was created
if exist "%desktop%\Diode Tester V5.lnk" (
    if not "%1"=="silent" (
        echo.
        echo SUCCESS: Professional shortcut created on desktop!
        echo.
        echo The shortcut will:
        echo - Launch with a professional console window
        echo - Show helpful error messages if Python is missing
        echo - Use the Diode Dynamics icon
        echo.
        pause
    )
    exit /b 0
) else (
    if not "%1"=="silent" (
        echo.
        echo ERROR: Could not create shortcut
        echo Please create manually
        echo.
        pause
    )
    exit /b 1
)