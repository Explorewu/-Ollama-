@echo off
rem 简化版诊断脚本，适用于trae-sandbox环境
set "DIAGNOSIS_TIME=%date% %time%"
set "REPORT_FILE=%~dp0ollama_diagnosis_report.txt"
set "OLLAMA_PORT=11434"
set "OLLAMA_HOST=localhost"
set "ISSUES_FOUND=0"

cls
echo ============================================
echo      Ollama Connection Diagnosis Tool
echo      Version: 1.0
echo ============================================
echo.

echo Ollama Diagnosis Report > "%REPORT_FILE%"
echo Generated: %DIAGNOSIS_TIME% >> "%REPORT_FILE%"
echo ============================================ >> "%REPORT_FILE%"
echo. >> "%REPORT_FILE%"

echo [START] Systematic diagnosis
echo.

echo [Step 1/5] Checking port %OLLAMA_PORT% usage...
echo. >> "%REPORT_FILE%"
echo [Step 1/5] Checking port %OLLAMA_PORT% usage... >> "%REPORT_FILE%"

netstat -ano | findstr :%OLLAMA_PORT%
echo. >> "%REPORT_FILE%"
netstat -ano | findstr :%OLLAMA_PORT% >> "%REPORT_FILE%"

echo [Step 2/5] Testing HTTP service...
echo. >> "%REPORT_FILE%"
echo [Step 2/5] Testing HTTP service... >> "%REPORT_FILE%"

echo     [TEST] GET http://%OLLAMA_HOST%:%OLLAMA_PORT%/api/tags
echo     [TEST] GET http://%OLLAMA_HOST%:%OLLAMA_PORT%/api/tags >> "%REPORT_FILE%"

powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%OLLAMA_HOST%:%OLLAMA_PORT%/api/tags' -TimeoutSec 5 -UseBasicParsing; Write-Host '     [OK] HTTP ' $response.StatusCode; Write-Host '     [OK] Service responding normally' } catch { Write-Host '     [ERROR] ' $_.Exception.Message }" 2>nul
echo. >> "%REPORT_FILE%"

powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%OLLAMA_HOST%:%OLLAMA_PORT%/api/tags' -TimeoutSec 5 -UseBasicParsing; Add-Content -Path '%REPORT_FILE%' -Value '     [OK] HTTP ' + $response.StatusCode; Add-Content -Path '%REPORT_FILE%' -Value '     [OK] Service responding normally' } catch { Add-Content -Path '%REPORT_FILE%' -Value '     [ERROR] ' + $_.Exception.Message }" 2>nul

echo [Step 3/5] Checking installed models...
echo. >> "%REPORT_FILE%"
echo [Step 3/5] Checking installed models... >> "%REPORT_FILE%"

echo     [EXEC] ollama list
echo     [EXEC] ollama list >> "%REPORT_FILE%"

powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%OLLAMA_HOST%:%OLLAMA_PORT%/api/tags' -TimeoutSec 5 -UseBasicParsing; $models = $response.Content | ConvertFrom-Json; $modelCount = $models.models.Count; Write-Host '     [OK] ' $modelCount ' model(s) installed'; foreach ($model in $models.models) { Write-Host '     [MODEL] ' $model.name } } catch { Write-Host '     [ERROR] Cannot get models' }" 2>nul
echo. >> "%REPORT_FILE%"

powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%OLLAMA_HOST%:%OLLAMA_PORT%/api/tags' -TimeoutSec 5 -UseBasicParsing; $models = $response.Content | ConvertFrom-Json; $modelCount = $models.models.Count; Add-Content -Path '%REPORT_FILE%' -Value '     [OK] ' + $modelCount + ' model(s) installed'; foreach ($model in $models.models) { Add-Content -Path '%REPORT_FILE%' -Value '     [MODEL] ' + $model.name } } catch { Add-Content -Path '%REPORT_FILE%' -Value '     [ERROR] Cannot get models' }" 2>nul

echo [Step 4/5] Checking system information...
echo. >> "%REPORT_FILE%"
echo [Step 4/5] Checking system information... >> "%REPORT_FILE%"

echo     [INFO] Operating System: %OS%
echo     [INFO] Operating System: %OS% >> "%REPORT_FILE%"

echo [Step 5/5] Summary...
echo. >> "%REPORT_FILE%"
echo [Step 5/5] Summary... >> "%REPORT_FILE%"

echo ============================================
echo   Diagnosis Summary
echo ============================================
echo.
echo. >> "%REPORT_FILE%"
echo ============================================ >> "%REPORT_FILE%"
echo   Diagnosis Summary >> "%REPORT_FILE%"
echo ============================================ >> "%REPORT_FILE%"

echo   Report saved to:
echo   %REPORT_FILE%
echo   Report saved to: %REPORT_FILE% >> "%REPORT_FILE%"
echo.
echo [Options]
echo   [1] Test connection again
echo   [Q] Quit
echo.
