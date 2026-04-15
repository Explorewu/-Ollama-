@echo off
setlocal
set ROOT=%~dp0
cd /d %ROOT%

set PYTHON=python

where %PYTHON% >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found in PATH.
  exit /b 1
)

echo [INFO] Starting intelligent_api...
start "intelligent_api" /B %PYTHON% server\intelligent_api.py

set START_VOICE=1
if /I "%1"=="no-voice" set START_VOICE=0

if %START_VOICE%==1 (
  echo [INFO] Starting voice_call_service...
  start "voice_call_service" /B %PYTHON% server\voice_call_service.py
) else (
  echo [INFO] Voice call service skipped.
)

echo [INFO] Services launched.
exit /b 0
