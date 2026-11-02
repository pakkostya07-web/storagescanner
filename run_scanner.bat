@echo off
cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python disk_scanner.py %*
    if errorlevel 1 pause
    exit /b
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py disk_scanner.py %*
    if errorlevel 1 pause
    exit /b
)

echo.
echo [ERROR] Python not found in PATH!
echo Please install Python from https://www.python.org/
echo.
pause
