@echo off
setlocal

title Ollama Assistant Launcher

set ROOT=%~dp0
cd /d %ROOT%

echo.
echo ================================================================
echo           Ollama Assistant - One-Click Launcher
echo ================================================================
echo   Backend API:  http://localhost:5001
echo   Frontend Web: http://localhost:8080
echo   Voice Service: ws://localhost:5005
echo ================================================================
echo.

set PYTHON=python
where %PYTHON% >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python first.
    pause
    exit /b 1
)

echo Launching detached services with health checks...
%PYTHON% "%ROOT%start_ollama_hub.py"
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Startup failed. Check logs in "%ROOT%logs".
    pause
    exit /b %EXIT_CODE%
)

echo.
echo Services are ready. Logs are in "%ROOT%logs".
echo Closing this window will not stop detached services.
echo.
pause
