@echo off
title Ollama Hub Stop
echo ==========================================
echo    Ollama Hub Stop All Services
echo ==========================================
echo.

echo [1/4] Stopping Backend API Service...
taskkill /FI "WINDOWTITLE eq BackendAPI*" /F >nul 2>&1
echo    Done
timeout /t 1 /nobreak >nul

echo [2/4] Stopping WebSocket Service...
taskkill /FI "WINDOWTITLE eq WebSocket*" /F >nul 2>&1
echo    Done
timeout /t 1 /nobreak >nul

echo [3/4] Stopping Frontend Web Server...
taskkill /FI "WINDOWTITLE eq WebServer*" /F >nul 2>&1
echo    Done
timeout /t 1 /nobreak >nul

echo [4/4] Stopping Ollama Service...
taskkill /FI "WINDOWTITLE eq Ollama Service*" /F >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo    Ollama service stopped
) else (
    echo    Ollama service not running
)
timeout /t 1 /nobreak >nul

echo.
echo ==========================================
echo    All Services Stopped!
echo ==========================================
echo.
pause
