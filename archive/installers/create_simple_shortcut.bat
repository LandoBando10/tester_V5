@echo off
echo Creating desktop shortcut for Diode Tester V5...
echo.

:: Detect desktop location
if exist "%USERPROFILE%\Desktop" (
    set "desktop=%USERPROFILE%\Desktop"
) else if exist "%USERPROFILE%\OneDrive\Desktop" (
    set "desktop=%USERPROFILE%\OneDrive\Desktop"
) else (
    echo ERROR: Could not find desktop!
    pause
    exit /b 1
)

:: Get python path
where python > temp_python_path.txt
set /p PYTHON_PATH=<temp_python_path.txt
del temp_python_path.txt

:: Create batch launcher
echo @echo off > "%~dp0DiodeTester.bat"
echo cd /d "%~dp0" >> "%~dp0DiodeTester.bat"
echo "%PYTHON_PATH%" main.py --shared-drive "B:\Users\Landon Epperson\Tester" >> "%~dp0DiodeTester.bat"

:: Create shortcut
powershell -Command ^
"$WshShell = New-Object -comObject WScript.Shell; ^
$Shortcut = $WshShell.CreateShortcut('%desktop%\Diode Tester V5.lnk'); ^
$Shortcut.TargetPath = '%~dp0DiodeTester.bat'; ^
$Shortcut.WorkingDirectory = '%~dp0'; ^
$Shortcut.Description = 'Diode Dynamics Production Tester V5'; ^
$Shortcut.IconLocation = '%~dp0resources\shortcut_icon.ico'; ^
$Shortcut.WindowStyle = 7; ^
$Shortcut.Save()"

echo.
echo Shortcut created on desktop!
echo.
pause