@echo off
cd /d "%~dp0"
python disk_scanner.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to run Storage Scanner.
    echo Please make sure Python and Matplotlib are installed.
    echo.
    pause
)
