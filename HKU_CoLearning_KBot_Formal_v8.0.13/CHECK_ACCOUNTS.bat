@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HKU Co-Learning KBot - Account Check
call scripts\windows_python.bat scripts\account_diagnostics.py
set "KBOT_RESULT=%ERRORLEVEL%"
echo.
echo This command only lists account names and roles. It never prints password hashes.
pause
exit /b %KBOT_RESULT%
