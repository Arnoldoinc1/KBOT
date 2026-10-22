@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HKU Co-Learning KBot - Setup Check
call scripts\windows_python.bat scripts\startup_check.py --service all
set "KBOT_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %KBOT_RESULT%
