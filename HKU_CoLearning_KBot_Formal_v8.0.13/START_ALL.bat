@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HKU Co-Learning KBot Launcher

echo [KBot] Running startup checks...
call scripts\windows_python.bat scripts\startup_check.py --service all
if errorlevel 1 goto :failed
call scripts\windows_python.bat scripts\migrate_db.py
if errorlevel 1 goto :failed

echo [KBot] Opening three service windows...
start "KBot Knowledge" cmd /k call "%CD%\scripts\windows_service_window.bat" knowledge
timeout /t 2 /nobreak >nul
start "KBot Teacher" cmd /k call "%CD%\scripts\windows_service_window.bat" teacher
start "KBot Student" cmd /k call "%CD%\scripts\windows_service_window.bat" student

echo [KBot] Knowledge API: http://127.0.0.1:5100/health
echo [KBot] Teacher:   http://127.0.0.1:5000/
echo [KBot] Student:   http://127.0.0.1:8000/
timeout /t 4 /nobreak >nul
exit /b 0

:failed
echo.
echo [KBot ERROR] Startup stopped. Read the error above.
pause
exit /b 1
