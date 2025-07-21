@echo off
echo ========================================
echo Simple Deployment for Diode Tester V5
echo ========================================
echo.

:: Set paths
set "SOURCE=%~dp0.."
set "DEST=B:\Users\Landon Epperson\Tester\DiodeTester_V5_Source"

echo Source: %SOURCE%
echo Destination: %DEST%
echo.

:: Remove old deployment if exists
if exist "%DEST%" (
    echo Removing old deployment...
    rmdir /S /Q "%DEST%"
)

:: Create destination
mkdir "%DEST%"

:: Copy all necessary directories and files
echo Copying source code...
xcopy "%SOURCE%\src" "%DEST%\src\" /E /I /Y /Q
if errorlevel 1 goto :error

echo Copying configuration...
xcopy "%SOURCE%\config" "%DEST%\config\" /E /I /Y /Q
if errorlevel 1 goto :error

echo Copying resources...
xcopy "%SOURCE%\resources" "%DEST%\resources\" /E /I /Y /Q
if errorlevel 1 goto :error

echo Copying firmware...
xcopy "%SOURCE%\firmware" "%DEST%\firmware\" /E /I /Y /Q
if errorlevel 1 goto :error

echo Copying documentation...
xcopy "%SOURCE%\docs" "%DEST%\docs\" /E /I /Y /Q
if errorlevel 1 goto :error

echo Copying deployment files...
xcopy "%SOURCE%\deployment" "%DEST%\deployment\" /E /I /Y /Q
if errorlevel 1 goto :error

:: Copy individual files
echo Copying main files...
copy "%SOURCE%\main.py" "%DEST%\" >nul
copy "%SOURCE%\requirements.txt" "%DEST%\" >nul
copy "%SOURCE%\VERSION" "%DEST%\" >nul 2>nul
copy "%SOURCE%\README.md" "%DEST%\" >nul 2>nul

:: Move installer files to root for easy access
echo Setting up installer...
:: Copy console installer
copy "%SOURCE%\deployment\INSTALL_CONSOLE.bat" "%DEST%\INSTALL_DiodeTester.bat" >nul
copy "%SOURCE%\install_console.py" "%DEST%\" >nul

:: Copy the new shortcut creator
if exist "%SOURCE%\create_shortcuts.bat" (
    copy "%SOURCE%\create_shortcuts.bat" "%DEST%\" >nul
) else (
    echo WARNING: create_shortcuts.bat not found!
)

:: Ensure icon file is copied with resources
if not exist "%DEST%\resources\shortcut_icon.ico" (
    echo WARNING: Icon file not found in resources!
)

echo.
echo ========================================
echo DEPLOYMENT COMPLETE!
echo ========================================
echo.
echo Deployed to: %DEST%
echo.
echo Users should:
echo 1. Navigate to: %DEST%
echo 2. Run: INSTALL_DiodeTester.bat
echo.
pause
exit /b 0

:error
echo.
echo ERROR: Deployment failed!
echo Please check that you have access to the shared drive.
echo.
pause
exit /b 1