@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
set "SERVICE=%~1"

if /I "%SERVICE%"=="knowledge" set "MODULE=knowledge_service.run"
if /I "%SERVICE%"=="teacher" set "MODULE=teacher_app.run"
if /I "%SERVICE%"=="student" set "MODULE=student_app.run"

if not defined MODULE (
  echo [KBot ERROR] Unknown service: %SERVICE%
  pause
  exit /b 2
)

call scripts\windows_python.bat scripts\startup_check.py --service %SERVICE%
if errorlevel 1 goto :failed
call scripts\windows_python.bat -m %MODULE%
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo [KBot ERROR] %SERVICE% did not start. Read the error above.
pause
exit /b 1
