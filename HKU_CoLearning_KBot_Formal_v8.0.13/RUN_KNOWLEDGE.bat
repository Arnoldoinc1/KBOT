@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HKU Co-Learning KBot - Knowledge Service
echo [KBot] Starting Knowledge Service at http://127.0.0.1:5100/
call scripts\windows_service_window.bat knowledge
exit /b %ERRORLEVEL%
