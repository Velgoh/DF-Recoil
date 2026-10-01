@echo off
title Delta Force // Recoil Compensator
cd /d "%~dp0"

echo ========================================================
echo   DELTA FORCE - RECOIL COMPENSATOR LAUNCHER
echo ========================================================
echo.

set PYTHON_CMD=
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=python
) else (
    where py >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set PYTHON_CMD=py
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python is not installed or not found in system PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Ensure "Add Python to PATH" is checked during installation.
    echo.
    pause
    exit /b 1
)

%PYTHON_CMD% -c "import cv2, numpy, PIL" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Installing required libraries (opencv-python, numpy, pillow)...
    %PYTHON_CMD% -m pip install -r "%~dp0core\requirements.txt"
    echo.
)

set PYTHON_RUNNER=%PYTHON_CMD%
where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set PYTHON_RUNNER=pythonw
)

echo [INFO] Launching Recoil Compensator GUI...
cd /d "%~dp0core"
start "" "%PYTHON_RUNNER%" app.py

exit /b 0
