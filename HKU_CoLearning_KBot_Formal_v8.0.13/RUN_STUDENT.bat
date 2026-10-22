@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HKU Co-Learning KBot - Student App
call scripts\windows_python.bat scripts\startup_check.py --service student
if errorlevel 1 goto :failed
call scripts\windows_python.bat scripts\migrate_db.py
if errorlevel 1 goto :failed
echo [KBot] Starting Student App at http://127.0.0.1:8000/
call scripts\windows_python.bat -m student_app.run
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo [KBot ERROR] Student App did not start. Read the error above.
pause
exit /b 1
