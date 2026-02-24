@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Ollama Hub Optimized Launcher v2.2
color 0E
cls

echo ============================================
echo      Ollama Hub - Local LLM Platform
echo      Version: 2.2 (Optimized)
echo      Optimized by AI Assistant
echo ============================================
echo.

set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "SERVER_DIR=%PROJECT_DIR%\server"
set "WEB_DIR=%PROJECT_DIR%\web"
set "OLLAMA_EXE=%PROJECT_DIR%\ollama.exe"

:: 服务端口配置
set "PORT_WEB=8080"
set "PORT_API=5001"
set "PORT_SUMMARY=5002"
set "PORT_VISION=5003"
set "PORT_NATIVE_IMAGE=5004"
set "PORT_OLLAMA=11434"

echo [Setup] Project directory: %PROJECT_DIR%
echo.

set "OLLAMA_RUNNING=0"
set "API_RUNNING=0"
set "SUMMARY_RUNNING=0"
set "VISION_RUNNING=0"
set "WEB_RUNNING=0"
set "NATIVE_IMAGE_RUNNING=0"
set "PORT_IN_USE="
set "PORT_READY=0"

:main_loop

:: ============================================
:: 步骤1: 检查 Ollama 服务 (端口 %PORT_OLLAMA%)
:: ============================================
echo [Step 1/7] Checking Ollama service (port %PORT_OLLAMA%)...
call :check_port %PORT_OLLAMA%
if defined PORT_IN_USE (
    echo     [OK] Ollama service is already running (PID: %PORT_IN_USE%)
    set "OLLAMA_RUNNING=1"
) else (
    if exist "%OLLAMA_EXE%" (
        echo     [Start] Starting Ollama service...
        start "Ollama Service" /B "%OLLAMA_EXE%" serve
        call :wait_for_port %PORT_OLLAMA% 15
        if !PORT_READY! equ 1 (
            echo     [OK] Ollama service started successfully
            set "OLLAMA_RUNNING=1"
        ) else (
            echo     [Warn] Ollama service may have failed to start
            set "OLLAMA_RUNNING=0"
        )
    ) else (
        echo     [Warn] Ollama executable not found: %OLLAMA_EXE%
        set "OLLAMA_RUNNING=0"
    )
)
echo.

:: ============================================
:: 步骤2: 检查后端 API 服务 (端口 %PORT_API%)
:: ============================================
echo [Step 2/7] Checking backend API service (port %PORT_API%)...
call :check_port %PORT_API%
if defined PORT_IN_USE (
    echo     [OK] Backend API is already running (PID: %PORT_IN_USE%)
    set "API_RUNNING=1"
) else (
    if exist "%SERVER_DIR%\intelligent_api.py" (
        echo     [Start] Starting backend API...
        cd /d "%SERVER_DIR%"
        start "API Server" /B python intelligent_api.py
        call :wait_for_port %PORT_API% 20
        if !PORT_READY! equ 1 (
            echo     [OK] Backend API started successfully
            set "API_RUNNING=1"
        ) else (
            echo     [Warn] Backend API may have failed to start
            set "API_RUNNING=0"
        )
    ) else (
        echo     [Warn] Backend API file not found: %SERVER_DIR%\intelligent_api.py
        set "API_RUNNING=0"
    )
)
echo.

:: ============================================
:: 步骤3: 检查 Summary API 服务 (端口 %PORT_SUMMARY%)
:: ============================================
echo [Step 3/7] Checking Summary API service (port %PORT_SUMMARY%)...
call :check_port %PORT_SUMMARY%
if defined PORT_IN_USE (
    echo     [OK] Summary API is already running (PID: %PORT_IN_USE%)
    set "SUMMARY_RUNNING=1"
) else (
    if exist "%SERVER_DIR%\summary_api.py" (
        echo     [Start] Starting Summary API...
        cd /d "%SERVER_DIR%"
        start "Summary API Server" /B python summary_api.py
        call :wait_for_port %PORT_SUMMARY% 15
        if !PORT_READY! equ 1 (
            echo     [OK] Summary API started successfully
            set "SUMMARY_RUNNING=1"
        ) else (
            echo     [Warn] Summary API may have failed to start
            set "SUMMARY_RUNNING=0"
        )
    ) else (
        echo     [Warn] Summary API file not found: %SERVER_DIR%\summary_api.py
        set "SUMMARY_RUNNING=0"
    )
)
echo.

:: ============================================
:: 步骤4: 检查 Vision API 服务 (端口 %PORT_VISION%)
:: ============================================
echo [Step 4/7] Checking Vision API service (port %PORT_VISION%)...
call :check_port %PORT_VISION%
if defined PORT_IN_USE (
    echo     [OK] Vision API is already running (PID: %PORT_IN_USE%)
    set "VISION_RUNNING=1"
) else (
    if exist "%SERVER_DIR%\qwen3_vl_service.py" (
        echo     [Start] Starting Vision API...
        cd /d "%SERVER_DIR%"
        start "Vision API Server" /B python qwen3_vl_service.py
        call :wait_for_port %PORT_VISION% 30
        if !PORT_READY! equ 1 (
            echo     [OK] Vision API started successfully
            set "VISION_RUNNING=1"
        ) else (
            echo     [Warn] Vision API may have failed to start
            set "VISION_RUNNING=0"
        )
    ) else (
        echo     [Warn] Vision API file not found: %SERVER_DIR%\qwen3_vl_service.py
        set "VISION_RUNNING=0"
    )
)
echo.

:: ============================================
:: 步骤5: 检查 Native Image API 服务 (端口 %PORT_NATIVE_IMAGE%)
:: ============================================
echo [Step 5/7] Checking Native Image API service (port %PORT_NATIVE_IMAGE%)...
call :check_port %PORT_NATIVE_IMAGE%
if defined PORT_IN_USE (
    echo     [OK] Native Image API is already running (PID: %PORT_IN_USE%)
    set "NATIVE_IMAGE_RUNNING=1"
) else (
    if exist "%SERVER_DIR%\llama_cpp_native_image_server.py" (
        echo     [Start] Starting Native Image API...
        cd /d "%SERVER_DIR%"
        start "Native Image API Server" /B python llama_cpp_native_image_server.py
        call :wait_for_port %PORT_NATIVE_IMAGE% 30
        if !PORT_READY! equ 1 (
            echo     [OK] Native Image API started successfully
            set "NATIVE_IMAGE_RUNNING=1"
        ) else (
            echo     [Warn] Native Image API may have failed to start
            set "NATIVE_IMAGE_RUNNING=0"
        )
    ) else (
        echo     [Info] Native Image API file not found: %SERVER_DIR%\llama_cpp_native_image_server.py
        echo     [Info] This is optional, continuing...
        set "NATIVE_IMAGE_RUNNING=0"
    )
)
echo.

:: ============================================
:: 步骤6: 检查 Web 服务器 (端口 %PORT_WEB%)
:: ============================================
echo [Step 6/7] Checking Web server (port %PORT_WEB%)...
call :check_port %PORT_WEB%
if defined PORT_IN_USE (
    echo     [OK] Web server is already running (PID: %PORT_IN_USE%)
    set "WEB_RUNNING=1"
) else (
    if exist "%WEB_DIR%\index.html" (
        echo     [Start] Starting Web server...
        cd /d "%WEB_DIR%"
        start "Web Server" /B python -m http.server %PORT_WEB%
        call :wait_for_port %PORT_WEB% 10
        if !PORT_READY! equ 1 (
            echo     [OK] Web server started successfully
            set "WEB_RUNNING=1"
        ) else (
            echo     [Warn] Web server may have failed to start
            set "WEB_RUNNING=0"
        )
    ) else (
        echo     [Warn] Web directory not found: %WEB_DIR%
        set "WEB_RUNNING=0"
    )
)
echo.

:: ============================================
:: 步骤7: 验证所有服务 API 端点
:: ============================================
echo [Step 7/7] Verifying service endpoints...
echo.

:: 检查 Ollama API
echo     [Verify] Ollama API (http://localhost:%PORT_OLLAMA%/api/tags)
curl -s -o nul -w "     [%%{http_code}] " http://localhost:%PORT_OLLAMA%/api/tags 2>nul
if %errorlevel% equ 0 (
    echo   - OK
) else (
    echo   - Failed
)

:: 检查 Backend API
echo     [Verify] Backend API (http://localhost:%PORT_API%/api/health)
curl -s -o nul -w "     [%%{http_code}] " http://localhost:%PORT_API%/api/health 2>nul
if %errorlevel% equ 0 (
    echo   - OK
) else (
    echo   - Failed
)

:: 检查 Vision API
echo     [Verify] Vision API (http://localhost:%PORT_VISION%/api/vision/status)
curl -s -o nul -w "     [%%{http_code}] " http://localhost:%PORT_VISION%/api/vision/status 2>nul
if %errorlevel% equ 0 (
    echo   - OK
) else (
    echo   - Failed
)

:: 检查 Summary API
echo     [Verify] Summary API (http://localhost:%PORT_SUMMARY%/api/summary/health)
curl -s -o nul -w "     [%%{http_code}] " http://localhost:%PORT_SUMMARY%/api/summary/health 2>nul
if %errorlevel% equ 0 (
    echo   - OK
) else (
    echo   - Failed
)

:: 检查 Native Image API
echo     [Verify] Native Image API (http://localhost:%PORT_NATIVE_IMAGE%/api/native_llama_cpp_image/health)
curl -s -o nul -w "     [%%{http_code}] " http://localhost:%PORT_NATIVE_IMAGE%/api/native_llama_cpp_image/health 2>nul
if %errorlevel% equ 0 (
    echo   - OK
) else (
    echo   - Failed
)
echo.

echo [Launch] Opening browser...
timeout /t 1 /nobreak >nul
start http://localhost:%PORT_WEB%
echo     [OK] Browser launched
echo.

echo ============================================
echo   All services ready! Status Summary:
echo ============================================
echo.
echo   Port    Service              Status
echo   -----   -------------------   ------
call :get_status_display %PORT_WEB% WEB_RUNNING
echo   %PORT_WEB%     Web Server           !STATUS_DISPLAY!
call :get_status_display %PORT_API% API_RUNNING
echo   %PORT_API%     Backend API          !STATUS_DISPLAY!
call :get_status_display %PORT_SUMMARY% SUMMARY_RUNNING
echo   %PORT_SUMMARY%     Summary API          !STATUS_DISPLAY!
call :get_status_display %PORT_VISION% VISION_RUNNING
echo   %PORT_VISION%     Vision API           !STATUS_DISPLAY!
call :get_status_display %PORT_NATIVE_IMAGE% NATIVE_IMAGE_RUNNING
echo   %PORT_NATIVE_IMAGE%     Native Image API     !STATUS_DISPLAY!
call :get_status_display %PORT_OLLAMA% OLLAMA_RUNNING
echo   %PORT_OLLAMA%     Ollama               !STATUS_DISPLAY!
echo.

echo Access URLs:
echo   - Web UI:    http://localhost:%PORT_WEB%
echo   - API Docs:  http://localhost:%PORT_API%/docs
echo   - Ollama:    http://localhost:%PORT_OLLAMA%
echo   - Vision:    http://localhost:%PORT_VISION%
echo   - Summary:   http://localhost:%PORT_SUMMARY%
echo   - Native Img:http://localhost:%PORT_NATIVE_IMAGE%
echo.
echo Features:
echo   [Enhanced] Improved service management
echo   [Smart]    Auto-detect running services
echo   [Health]   API endpoint verification
echo   [Memory]   Conversation history saved
echo.
echo Quick Actions:
echo   [D] Create desktop shortcut
echo   [S] Stop all services
echo   [R] Restart services
echo   [Q] Quit
echo.

choice /c DSQR /n /m "Select action (D=Shortcut, S=Stop, Q=Quit, R=Restart): " /t 30 /d Q

if %errorlevel% equ 1 (
    echo.
    echo [Shortcut] Creating desktop shortcut...
    for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%I"
    (
        echo [InternetShortcut]
        echo URL=http://localhost:%PORT_WEB%
        echo IconFile=%PROJECT_DIR%\ollama.exe
        echo IconIndex=0
    ) > "%DESKTOP%\Ollama Hub.url"
    echo [OK] Desktop shortcut created: %DESKTOP%\Ollama Hub.url
    goto :end
)

if %errorlevel% equ 2 (
    echo.
    echo [Stop] Stopping all services...
    call :kill_port %PORT_WEB%
    call :kill_port %PORT_API%
    call :kill_port %PORT_SUMMARY%
    call :kill_port %PORT_VISION%
    call :kill_port %PORT_NATIVE_IMAGE%
    call :kill_port %PORT_OLLAMA%
    echo [OK] All services stopped
    pause
    goto :end
)

if %errorlevel% equ 3 (
    goto :end
)

if %errorlevel% equ 4 (
    echo.
    echo [Restart] Restarting all services...
    call :kill_port %PORT_WEB%
    call :kill_port %PORT_API%
    call :kill_port %PORT_SUMMARY%
    call :kill_port %PORT_VISION%
    call :kill_port %PORT_NATIVE_IMAGE%
    call :kill_port %PORT_OLLAMA%
    timeout /t 2 /nobreak >nul
    echo [Restart] Starting services again...
    goto :restart_services
)

:end
echo.
echo Tips:
echo   - Closing this window won't stop services (background mode)
echo   - Run again to connect to existing services
echo   - Select S to stop services, R to restart
echo.
pause
goto :eof

:: ============================================
:: 检查端口是否被占用
:: 参数: 端口号
:: 设置变量: PORT_IN_USE (如果端口被占用)
:: ============================================
:check_port
set "PORT_IN_USE="
set "CHECK_PORT=%~1"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%CHECK_PORT% .*LISTENING"') do (
    set "PORT_IN_USE=%%P"
    goto :check_port_done
)
:check_port_done
if defined PORT_IN_USE (
    set "PORT_IN_USE=%PORT_IN_USE: =%"
)
exit /b 0

:: ============================================
:: 等待端口就绪
:: 参数: 端口号, 超时秒数
:: 设置变量: PORT_READY (1=就绪, 0=超时)
:: ============================================
:wait_for_port
set "PORT_READY=0"
set "WAIT_PORT=%~1"
set "WAIT_TIMEOUT=%~2"
if "%WAIT_TIMEOUT%"=="" set "WAIT_TIMEOUT=10"

for /L %%i in (1,1,%WAIT_TIMEOUT%) do (
    call :check_port %WAIT_PORT%
    if defined PORT_IN_USE (
        set "PORT_READY=1"
        goto :wait_done
    )
    timeout /t 1 /nobreak >nul
)
:wait_done
exit /b 0

:: ============================================
:: 终止指定端口的进程 (改进版)
:: 参数: 端口号
:: ============================================
:kill_port
set "KILL_PORT=%~1"
if "%KILL_PORT%"=="" exit /b 1

echo     [Kill] Terminating process on port %KILL_PORT%...

:: 获取端口对应的进程ID
set "FOUND_PIDS="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%KILL_PORT% .*LISTENING"') do (
    set "FOUND_PIDS=!FOUND_PIDS! %%P"
)

:: 如果没有找到进程，直接返回
if "!FOUND_PIDS!"=="" (
    echo           No process found on port %KILL_PORT%
    exit /b 0
)

:: 尝试终止每个找到的进程
for %%P in (!FOUND_PIDS!) do (
    :: 验证进程是否存在
    tasklist /FI "PID eq %%P" /FO CSV /NH 2>nul | findstr /I "%%P" >nul
    if !errorlevel! equ 0 (
        echo           Stopping PID %%P...
        taskkill /F /PID %%P >nul 2>&1
        if !errorlevel! equ 0 (
            echo           [OK] PID %%P terminated
        ) else (
            echo           [Warn] Failed to stop PID %%P
        )
    )
)

:: 等待端口释放
timeout /t 1 /nobreak >nul

:: 验证端口已释放
call :check_port %KILL_PORT%
if defined PORT_IN_USE (
    echo           [Warn] Port %KILL_PORT% still in use
) else (
    echo           [OK] Port %KILL_PORT% released
)
exit /b 0

:: ============================================
:: 重新启动服务入口点
:: ============================================
:restart_services
set "OLLAMA_RUNNING=0"
set "API_RUNNING=0"
set "SUMMARY_RUNNING=0"
set "VISION_RUNNING=0"
set "WEB_RUNNING=0"
set "NATIVE_IMAGE_RUNNING=0"
goto :main_loop

:: ============================================
:: 获取状态显示文本
:: 参数: 端口号, 状态变量名
:: 设置变量: STATUS_DISPLAY
:: ============================================
:get_status_display
set "CHECK_PORT=%~1"
set "STATUS_VAR=%~2"
call :check_port %CHECK_PORT%
if defined PORT_IN_USE (
    set "STATUS_DISPLAY=Running"
) else (
    set "STATUS_DISPLAY=Stopped"
)
exit /b 0