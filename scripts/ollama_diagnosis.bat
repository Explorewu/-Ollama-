@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Ollama 连接诊断工具 v1.0
color 0B
cls

echo ============================================
echo      Ollama 连接诊断工具
echo      Version: 1.0
echo      功能: 系统性排查连接问题
echo ============================================
echo.

set "DIAGNOSIS_TIME=%date% %time%"
set "REPORT_FILE=%~dp0ollama_diagnosis_report.txt"
set "OLLAMA_PORT=11434"
set "OLLAMA_HOST=localhost"
set "ISSUES_FOUND=0"

:: 初始化报告
echo Ollama 连接诊断报告 > "%REPORT_FILE%"
echo 生成时间: %DIAGNOSIS_TIME% >> "%REPORT_FILE%"
echo ============================================ >> "%REPORT_FILE%"
echo. >> "%REPORT_FILE%"

echo [开始] 系统性诊断流程
echo.

:: ============================================
:: 步骤1: 检查 Ollama 安装
:: ============================================
echo [步骤 1/8] 检查 Ollama 安装...
echo. >> "%REPORT_FILE%"
echo [步骤 1/8] 检查 Ollama 安装... >> "%REPORT_FILE%"

set "OLLAMA_EXE="
set "OLLAMA_FOUND=0"

:: 检查常见安装位置
for %%P in (
    "%~dp0ollama.exe"
    "C:\Program Files\Ollama\ollama.exe"
    "C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama.exe"
) do (
    if exist %%P (
        set "OLLAMA_EXE=%%~P"
        set "OLLAMA_FOUND=1"
        echo     [OK] 找到 Ollama: %%~P
        echo     [OK] 找到 Ollama: %%~P >> "%REPORT_FILE%"
        goto :ollama_found
    )
)

:: 检查环境变量
for /f "delims=" %%I in ('where ollama 2^>nul') do (
    set "OLLAMA_EXE=%%I"
    set "OLLAMA_FOUND=1"
    echo     [OK] 找到 Ollama (PATH): %%I
    echo     [OK] 找到 Ollama (PATH): %%I >> "%REPORT_FILE%"
    goto :ollama_found
)

:ollama_found
if %OLLAMA_FOUND% equ 0 (
    echo     [错误] 未找到 Ollama 安装
    echo     [错误] 未找到 Ollama 安装 >> "%REPORT_FILE%"
    echo     [建议] 请从 https://ollama.com 下载并安装 Ollama
    echo     [建议] 请从 https://ollama.com 下载并安装 Ollama >> "%REPORT_FILE%"
    set /a ISSUES_FOUND+=1
) else (
    :: 检查版本
    for /f "delims=" %%V in ('"%OLLAMA_EXE%" --version 2^>nul') do (
        echo     [信息] 版本: %%V
        echo     [信息] 版本: %%V >> "%REPORT_FILE%"
    )
)
echo.

:: ============================================
:: 步骤2: 检查环境变量
:: ============================================
echo [步骤 2/8] 检查环境变量配置...
echo. >> "%REPORT_FILE%"
echo [步骤 2/8] 检查环境变量配置... >> "%REPORT_FILE%"

:: 检查 OLLAMA_HOST
echo     [检查] OLLAMA_HOST 环境变量
echo     [检查] OLLAMA_HOST 环境变量 >> "%REPORT_FILE%"
if defined OLLAMA_HOST (
    echo     [信息] OLLAMA_HOST=%OLLAMA_HOST%
    echo     [信息] OLLAMA_HOST=%OLLAMA_HOST% >> "%REPORT_FILE%"
    if not "%OLLAMA_HOST%"=="127.0.0.1:%OLLAMA_PORT%" (
        if not "%OLLAMA_HOST%"=="localhost:%OLLAMA_PORT%" (
            echo     [警告] OLLAMA_HOST 设置非标准值，可能导致连接问题
            echo     [警告] OLLAMA_HOST 设置非标准值，可能导致连接问题 >> "%REPORT_FILE%"
            echo     [建议] 如需使用默认端口，请执行: setx OLLAMA_HOST "127.0.0.1:%OLLAMA_PORT%"
            echo     [建议] 如需使用默认端口，请执行: setx OLLAMA_HOST "127.0.0.1:%OLLAMA_PORT%" >> "%REPORT_FILE%"
            set /a ISSUES_FOUND+=1
        )
    )
) else (
    echo     [OK] 使用默认配置 (127.0.0.1:%OLLAMA_PORT%)
    echo     [OK] 使用默认配置 (127.0.0.1:%OLLAMA_PORT%) >> "%REPORT_FILE%"
)

:: 检查 OLLAMA_MODELS
echo     [检查] OLLAMA_MODELS 环境变量
echo     [检查] OLLAMA_MODELS 环境变量 >> "%REPORT_FILE%"
if defined OLLAMA_MODELS (
    echo     [信息] OLLAMA_MODELS=%OLLAMA_MODELS%
    echo     [信息] OLLAMA_MODELS=%OLLAMA_MODELS% >> "%REPORT_FILE%"
    if not exist "%OLLAMA_MODELS%" (
        echo     [警告] 模型目录不存在: %OLLAMA_MODELS%
        echo     [警告] 模型目录不存在: %OLLAMA_MODELS% >> "%REPORT_FILE%"
        set /a ISSUES_FOUND+=1
    )
) else (
    echo     [信息] 使用默认模型目录
    echo     [信息] 使用默认模型目录 >> "%REPORT_FILE%"
)
echo.

:: ============================================
:: 步骤3: 检查端口占用情况
:: ============================================
echo [步骤 3/8] 检查端口 %OLLAMA_PORT% 占用情况...
echo. >> "%REPORT_FILE%"
echo [步骤 3/8] 检查端口 %OLLAMA_PORT% 占用情况... >> "%REPORT_FILE%"

set "PORT_PID="
set "PORT_PROCESS="

for /f "tokens=2,5" %%A in ('netstat -ano ^| findstr /R /C:":%OLLAMA_PORT% .*LISTENING"') do (
    set "PORT_PID=%%B"
    goto :port_found
)

:port_found
if defined PORT_PID (
    echo     [信息] 端口 %OLLAMA_PORT% 被占用 (PID: %PORT_PID%)
    echo     [信息] 端口 %OLLAMA_PORT% 被占用 (PID: %PORT_PID%) >> "%REPORT_FILE%"
    
    :: 获取进程名
    for /f "delims=" %%P in ('tasklist /FI "PID eq %PORT_PID%" /FO CSV /NH 2^>nul') do (
        set "PORT_PROCESS=%%P"
        echo     [信息] 占用进程: %%P
        echo     [信息] 占用进程: %%P >> "%REPORT_FILE%"
    )
    
    :: 检查是否是 Ollama
    echo %PORT_PROCESS% | findstr /I "ollama" >nul
    if errorlevel 1 (
        echo     [警告] 端口被非 Ollama 进程占用！
        echo     [警告] 端口被非 Ollama 进程占用！ >> "%REPORT_FILE%"
        echo     [建议] 请关闭占用端口的程序或修改 Ollama 端口
        set /a ISSUES_FOUND+=1
    ) else (
        echo     [OK] 端口被 Ollama 进程占用
        echo     [OK] 端口被 Ollama 进程占用 >> "%REPORT_FILE%"
    )
) else (
    echo     [警告] 端口 %OLLAMA_PORT% 未被占用
    echo     [警告] 端口 %OLLAMA_PORT% 未被占用 >> "%REPORT_FILE%"
    echo     [建议] Ollama 服务可能未启动
    set /a ISSUES_FOUND+=1
)
echo.

:: ============================================
:: 步骤4: 网络连接测试
:: ============================================
echo [步骤 4/8] 测试网络连接...
echo. >> "%REPORT_FILE%"
echo [步骤 4/8] 测试网络连接... >> "%REPORT_FILE%"

:: 使用 PowerShell 测试连接
echo     [测试] 连接到 %OLLAMA_HOST%:%OLLAMA_PORT%
echo     [测试] 连接到 %OLLAMA_HOST%:%OLLAMA_PORT% >> "%REPORT_FILE%"

powershell -NoProfile -Command "
try {
    $client = New-Object System.Net.Sockets.TcpClient
    $client.Connect('%OLLAMA_HOST%', %OLLAMA_PORT%)
    if ($client.Connected) {
        Write-Host '     [OK] TCP 连接成功'
        $client.Close()
        exit 0
    }
} catch {
    Write-Host ('     [失败] TCP 连接失败: ' + $_.Exception.Message)
    exit 1
}
" 2>nul

if errorlevel 1 (
    echo     [错误] 无法建立 TCP 连接
    echo     [错误] 无法建立 TCP 连接 >> "%REPORT_FILE%"
    set /a ISSUES_FOUND+=1
) else (
    echo     [OK] TCP 连接正常
    echo     [OK] TCP 连接正常 >> "%REPORT_FILE%"
)
echo.

:: ============================================
:: 步骤5: HTTP 服务测试
:: ============================================
echo [步骤 5/8] 测试 HTTP 服务响应...
echo. >> "%REPORT_FILE%"
echo [步骤 5/8] 测试 HTTP 服务响应... >> "%REPORT_FILE%"

echo     [测试] GET http://%OLLAMA_HOST%:%OLLAMA_PORT%/api/tags
echo     [测试] GET http://%OLLAMA_HOST%:%OLLAMA_PORT%/api/tags >> "%REPORT_FILE%"

powershell -NoProfile -Command "
try {
    $response = Invoke-WebRequest -Uri 'http://%OLLAMA_HOST%:%OLLAMA_PORT%/api/tags' -TimeoutSec 5 -UseBasicParsing
    Write-Host ('     [OK] HTTP ' + $response.StatusCode)
    Write-Host '     [OK] 服务响应正常'
    exit 0
} catch [System.Net.WebException] {
    if ($_.Exception.Response) {
        $status = [int]$_.Exception.Response.StatusCode
        Write-Host ('     [警告] HTTP ' + $status)
    } else {
        Write-Host '     [错误] 无法连接到服务'
    }
    exit 1
} catch {
    Write-Host ('     [错误] ' + $_.Exception.Message)
    exit 1
}
" 2>nul

if errorlevel 1 (
    echo     [错误] HTTP 服务测试失败
    echo     [错误] HTTP 服务测试失败 >> "%REPORT_FILE%"
    set /a ISSUES_FOUND+=1
)
echo.

:: ============================================
:: 步骤6: 防火墙检查
:: ============================================
echo [步骤 6/8] 检查 Windows 防火墙设置...
echo. >> "%REPORT_FILE%"
echo [步骤 6/8] 检查 Windows 防火墙设置... >> "%REPORT_FILE%"

:: 检查防火墙状态
for /f "delims=" %%F in ('powershell -NoProfile -Command "(Get-NetFirewallProfile).Enabled -contains \$true" 2^>nul') do (
    if "%%F"=="True" (
        echo     [信息] Windows 防火墙已启用
        echo     [信息] Windows 防火墙已启用 >> "%REPORT_FILE%"
        
        :: 检查 Ollama 规则
        netsh advfirewall firewall show rule name="Ollama" >nul 2>&1
        if errorlevel 1 (
            echo     [警告] 未找到 Ollama 防火墙规则
            echo     [警告] 未找到 Ollama 防火墙规则 >> "%REPORT_FILE%"
            echo     [建议] 可能需要手动添加规则允许端口 %OLLAMA_PORT%
            echo     [建议] 可能需要手动添加规则允许端口 %OLLAMA_PORT% >> "%REPORT_FILE%"
        ) else (
            echo     [OK] 找到 Ollama 防火墙规则
            echo     [OK] 找到 Ollama 防火墙规则 >> "%REPORT_FILE%"
        )
    ) else (
        echo     [信息] Windows 防火墙未启用
        echo     [信息] Windows 防火墙未启用 >> "%REPORT_FILE%"
    )
)
echo.

:: ============================================
:: 步骤7: 检查系统资源
:: ============================================
echo [步骤 7/8] 检查系统资源...
echo. >> "%REPORT_FILE%"
echo [步骤 7/8] 检查系统资源... >> "%REPORT_FILE%"

:: 内存
for /f "skip=1" %%M in ('wmic ComputerSystem get TotalPhysicalMemory') do (
    if not defined TOTAL_MEM set "TOTAL_MEM=%%M"
)
if defined TOTAL_MEM (
    set /a MEM_GB=%TOTAL_MEM:~0,-9%
    echo     [信息] 总内存: !MEM_GB! GB
    echo     [信息] 总内存: !MEM_GB! GB >> "%REPORT_FILE%"
    if !MEM_GB! LSS 8 (
        echo     [警告] 内存不足 8GB，可能影响模型运行
        echo     [警告] 内存不足 8GB，可能影响模型运行 >> "%REPORT_FILE%"
        set /a ISSUES_FOUND+=1
    )
)

:: 磁盘空间
for /f "tokens=3" %%D in ('wmic LogicalDisk where "DeviceID='C:'" get FreeSpace ^| findstr /V "FreeSpace"') do (
    set "FREE_SPACE=%%D"
    set /a FREE_GB=!FREE_SPACE:~0,-9!
    echo     [信息] C盘可用空间: !FREE_GB! GB
    echo     [信息] C盘可用空间: !FREE_GB! GB >> "%REPORT_FILE%"
    if !FREE_GB! LSS 10 (
        echo     [警告] 磁盘空间不足 10GB
        echo     [警告] 磁盘空间不足 10GB >> "%REPORT_FILE%"
        set /a ISSUES_FOUND+=1
    )
)
echo.

:: ============================================
:: 步骤8: 检查模型列表
:: ============================================
echo [步骤 8/8] 检查已安装模型...
echo. >> "%REPORT_FILE%"
echo [步骤 8/8] 检查已安装模型... >> "%REPORT_FILE%"

if %OLLAMA_FOUND% equ 1 (
    echo     [执行] ollama list
    echo     [执行] ollama list >> "%REPORT_FILE%"
    
    for /f "skip=1 delims=" %%M in ('"%OLLAMA_EXE%" list 2^>nul') do (
        echo     [模型] %%M
        echo     [模型] %%M >> "%REPORT_FILE%"
    )
    
    :: 检查是否有模型
    for /f %%C in ('"%OLLAMA_EXE%" list 2^>nul ^| find /c /v ""') do (
        if %%C LEQ 1 (
            echo     [警告] 未安装任何模型
            echo     [警告] 未安装任何模型 >> "%REPORT_FILE%"
            echo     [建议] 使用命令安装模型: ollama pull qwen:7b
            echo     [建议] 使用命令安装模型: ollama pull qwen:7b >> "%REPORT_FILE%"
            set /a ISSUES_FOUND+=1
        ) else (
            echo     [OK] 已安装 %%C 个模型
            echo     [OK] 已安装 %%C 个模型 >> "%REPORT_FILE%"
        )
    )
) else (
    echo     [跳过] Ollama 未安装，无法检查模型
    echo     [跳过] Ollama 未安装，无法检查模型 >> "%REPORT_FILE%"
)
echo.

:: ============================================
:: 诊断总结
:: ============================================
echo ============================================
echo   诊断总结
echo ============================================
echo.
echo. >> "%REPORT_FILE%"
echo ============================================ >> "%REPORT_FILE%"
echo   诊断总结 >> "%REPORT_FILE%"
echo ============================================ >> "%REPORT_FILE%"

if %ISSUES_FOUND% equ 0 (
    color 0A
    echo   [全部通过] 未发现连接问题！
    echo   [全部通过] 未发现连接问题！ >> "%REPORT_FILE%"
    echo.
    echo   Ollama 服务运行正常，可以正常使用。
    echo   Ollama 服务运行正常，可以正常使用。 >> "%REPORT_FILE%"
) else (
    color 0C
    echo   [发现问题] 发现 %ISSUES_FOUND% 个潜在问题
    echo   [发现问题] 发现 %ISSUES_FOUND% 个潜在问题 >> "%REPORT_FILE%"
    echo.
    echo   请根据上述诊断结果进行修复。
    echo   请根据上述诊断结果进行修复。 >> "%REPORT_FILE%"
)

echo.
echo   详细报告已保存至:
echo   %REPORT_FILE%
echo   详细报告已保存至: %REPORT_FILE% >> "%REPORT_FILE%"
echo.

:: 提供修复选项
echo [选项]
echo   [1] 尝试自动修复常见问题
echo   [2] 启动 Ollama 服务
echo   [3] 重新运行诊断
echo   [Q] 退出
echo.

choice /c 123Q /n /m "请选择操作 (1-3, Q=退出): "

if %errorlevel% equ 1 (
    echo.
    echo [自动修复] 正在尝试修复常见问题...
    call :auto_fix
    pause
    goto :eof
)

if %errorlevel% equ 2 (
    echo.
    echo [启动服务] 正在启动 Ollama...
    if %OLLAMA_FOUND% equ 1 (
        start "Ollama Service" /B "%OLLAMA_EXE%" serve
        echo [OK] Ollama 已启动，请等待 10 秒后重新运行诊断
        timeout /t 10 /nobreak >nul
    ) else (
        echo [错误] 未找到 Ollama 可执行文件
    )
    pause
    goto :eof
)

if %errorlevel% equ 3 (
    echo.
    echo [重新诊断] 重新运行诊断...
    goto :main_loop
)

if %errorlevel% equ 4 (
    goto :eof
)

:: ============================================
:: 子程序: 自动修复
:: ============================================
:auto_fix
echo.
echo [自动修复] 开始执行修复操作...
echo.

set "FIXES_APPLIED=0"

:: 修复1: 启动 Ollama 服务（如果未运行）
echo [修复 1/4] 检查并启动 Ollama 服务...
netstat -ano | findstr /R /C:":%OLLAMA_PORT% .*LISTENING" >nul
if errorlevel 1 (
    if %OLLAMA_FOUND% equ 1 (
        echo     [执行] 启动 Ollama 服务...
        start "Ollama Service" /B "%OLLAMA_EXE%" serve
        timeout /t 5 /nobreak >nul
        
        :: 验证启动
        netstat -ano | findstr /R /C:":%OLLAMA_PORT% .*LISTENING" >nul
        if errorlevel 0 (
            echo     [OK] Ollama 服务已启动
            set /a FIXES_APPLIED+=1
        ) else (
            echo     [失败] 服务启动失败，请手动检查
        )
    ) else (
        echo     [跳过] Ollama 未安装
    )
) else (
    echo     [跳过] 服务已在运行
)

:: 修复2: 添加防火墙规则
echo [修复 2/4] 检查并添加防火墙规则...
netsh advfirewall firewall show rule name="Ollama" >nul 2>&1
if errorlevel 1 (
    echo     [执行] 添加 Ollama 防火墙规则...
    netsh advfirewall firewall add rule name="Ollama" dir=in action=allow protocol=TCP localport=%OLLAMA_PORT% >nul 2>&1
    if errorlevel 0 (
        echo     [OK] 防火墙规则已添加
        set /a FIXES_APPLIED+=1
    ) else (
        echo     [失败] 需要管理员权限，请以管理员身份运行
    )
) else (
    echo     [跳过] 防火墙规则已存在
)

:: 修复3: 重置环境变量（如果设置错误）
echo [修复 3/4] 检查环境变量...
if defined OLLAMA_HOST (
    echo     [信息] OLLAMA_HOST=%OLLAMA_HOST%
    echo     [建议] 如需重置为默认值，请执行: setx OLLAMA_HOST ""
) else (
    echo     [跳过] 使用默认配置
)

:: 修复4: 测试连接
echo [修复 4/4] 测试连接...
timeout /t 3 /nobreak >nul
echo     [测试] 连接到 Ollama...

powershell -NoProfile -Command "
try {
    $response = Invoke-WebRequest -Uri 'http://localhost:%OLLAMA_PORT%/api/tags' -TimeoutSec 5 -UseBasicParsing
    Write-Host '     [OK] 连接成功 (HTTP ' $response.StatusCode ')'
    exit 0
} catch {
    Write-Host '     [失败] 连接失败'
    exit 1
}
" 2>nul

if errorlevel 0 (
    set /a FIXES_APPLIED+=1
)

echo.
echo [修复完成] 已应用 %FIXES_APPLIED% 项修复
echo.
echo [建议] 请重新运行诊断工具验证修复效果
echo.

exit /b 0

:main_loop
:: 重新运行诊断
call "%~f0"
goto :eof
