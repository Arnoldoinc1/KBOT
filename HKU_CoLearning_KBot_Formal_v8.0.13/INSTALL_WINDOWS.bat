@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HKU Co-Learning KBot - Install Dependencies
echo [KBot] Installing Python dependencies from requirements.txt...
call scripts\windows_python.bat -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo.
echo [KBot] Dependencies installed successfully.
pause
exit /b 0

:failed
echo.
echo [KBot ERROR] Dependency installation failed. Read the pip error above.
pause
exit /b 1
