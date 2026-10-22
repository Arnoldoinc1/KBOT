@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "KBOT_PY_EXE="
set "KBOT_PY_PREFIX="

if defined KBOT_PYTHON if exist "%KBOT_PYTHON%" set "KBOT_PY_EXE=%KBOT_PYTHON%"
if not defined KBOT_PY_EXE if exist ".venv\Scripts\python.exe" set "KBOT_PY_EXE=%CD%\.venv\Scripts\python.exe"
if not defined KBOT_PY_EXE if exist "venv\Scripts\python.exe" set "KBOT_PY_EXE=%CD%\venv\Scripts\python.exe"
if not defined KBOT_PY_EXE if exist "D:\Python3.11.9\python.exe" set "KBOT_PY_EXE=D:\Python3.11.9\python.exe"
if not defined KBOT_PY_EXE if exist "C:\Python3.11.9\python.exe" set "KBOT_PY_EXE=C:\Python3.11.9\python.exe"

if not defined KBOT_PY_EXE (
  for /f "delims=" %%P in ('where py 2^>nul') do if not defined KBOT_PY_EXE (
    set "KBOT_PY_EXE=%%P"
    set "KBOT_PY_PREFIX=-3.11"
  )
)
if not defined KBOT_PY_EXE (
  for /f "delims=" %%P in ('where python 2^>nul') do if not defined KBOT_PY_EXE set "KBOT_PY_EXE=%%P"
)

if not defined KBOT_PY_EXE (
  echo [KBot ERROR] Python was not found.
  echo Set KBOT_PYTHON to the full python.exe path, for example:
  echo   set KBOT_PYTHON=D:\Python3.11.9\python.exe
  exit /b 9009
)

set "PYTHONPATH=%CD%;%PYTHONPATH%"
if defined KBOT_PY_PREFIX (
  "%KBOT_PY_EXE%" %KBOT_PY_PREFIX% %*
) else (
  "%KBOT_PY_EXE%" %*
)
exit /b %ERRORLEVEL%
