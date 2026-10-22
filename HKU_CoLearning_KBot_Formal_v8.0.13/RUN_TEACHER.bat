@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HKU Co-Learning KBot - Teacher App
call scripts\windows_python.bat scripts\startup_check.py --service teacher
if errorlevel 1 goto :failed
call scripts\windows_python.bat scripts\migrate_db.py
if errorlevel 1 goto :failed
echo [KBot] Starting Teacher App at http://127.0.0.1:5000/
call scripts\windows_python.bat -m teacher_app.run
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo [KBot ERROR] Teacher App did not start. Read the error above.
pause
exit /b 1
