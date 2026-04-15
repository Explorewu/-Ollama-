param(
    [string]$HostName = "localhost",
    [int]$TimeoutSec = 6
)

$checks = @(
    @{ Name = "Ollama"; Url = "http://$HostName`:11434/api/tags" },
    @{ Name = "Backend Health"; Url = "http://$HostName`:5001/api/health" },
    @{ Name = "Vision Status"; Url = "http://$HostName`:5003/api/vision/status" },
    @{ Name = "Image Models"; Url = "http://$HostName`:5001/api/image/models" },
    @{ Name = "Web UI"; Url = "http://$HostName`:8080/index.html" }
)

$failed = @()

foreach ($check in $checks) {
    try {
        $resp = Invoke-WebRequest -Uri $check.Url -TimeoutSec $TimeoutSec -UseBasicParsing
        if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
            Write-Host "[OK] $($check.Name): $($resp.StatusCode) - $($check.Url)"
        } else {
            Write-Host "[FAIL] $($check.Name): $($resp.StatusCode) - $($check.Url)"
            $failed += $check.Name
        }
    } catch {
        Write-Host "[FAIL] $($check.Name): $($_.Exception.Message) - $($check.Url)"
        $failed += $check.Name
    }
}

if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "Smoke test failed: $($failed -join ', ')"
    exit 1
}

Write-Host ""
Write-Host "Smoke test passed."
exit 0
