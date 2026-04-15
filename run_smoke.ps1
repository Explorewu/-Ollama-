$ErrorActionPreference = 'Continue'
$base = "http://127.0.0.1:5001"
$script:results = @()

function Add-Result($name, $ok, $detail) {
  $script:results += [PSCustomObject]@{ Name=$name; OK=$ok; Detail=$detail }
}

function Try-Request($name, $method, $url, $body=$null) {
  try {
    $params = @{ Method=$method; Uri=$url; TimeoutSec=8 }
    if ($body -ne $null) {
      $params.Body = ($body | ConvertTo-Json -Depth 6)
      $params.ContentType = 'application/json'
    }
    $resp = Invoke-RestMethod @params
    Add-Result $name $true ("OK")
    return $resp
  } catch {
    Add-Result $name $false ($_.Exception.Message)
    return $null
  }
}

Try-Request "api.health" "GET" "$base/api/health" | Out-Null
Try-Request "api.health.detailed" "GET" "$base/api/health/detailed" | Out-Null

$chatResp = Try-Request "api.chat" "POST" "$base/api/chat" @{
  model = "qwen3.5"
  messages = @(@{ role="user"; content="hello" })
  stream = $false
}
if ($chatResp -ne $null -and $chatResp.data -and $chatResp.data.response) {
  Add-Result "api.chat.response" $true "has response"
} else {
  Add-Result "api.chat.response" $false "missing data.response"
}

Try-Request "group.health" "GET" "$base/api/group_chat/health" | Out-Null
Try-Request "group.status" "GET" "$base/api/group_chat/status" | Out-Null
Try-Request "group.emotions" "GET" "$base/api/group_chat/emotions" | Out-Null
Try-Request "group.viewpoints" "GET" "$base/api/group_chat/viewpoints" | Out-Null
Try-Request "group.world.get" "GET" "$base/api/group_chat/world_setting" | Out-Null
Try-Request "group.config" "POST" "$base/api/group_chat/config" @{ max_turns = 5; auto_stop = $true } | Out-Null
Try-Request "group.start" "POST" "$base/api/group_chat/auto_chat/start" @{ topic = "smoke test" } | Out-Null
Start-Sleep -Milliseconds 300
Try-Request "group.pause" "POST" "$base/api/group_chat/auto_chat/pause" | Out-Null
Try-Request "group.resume" "POST" "$base/api/group_chat/auto_chat/resume" | Out-Null
Try-Request "group.stop" "POST" "$base/api/group_chat/auto_chat/stop" @{ reason = "smoke" } | Out-Null

Try-Request "search.web" "POST" "$base/api/search/web" @{ query = "hello" } | Out-Null
Try-Request "search.instant" "POST" "$base/api/search/instant" @{ query = "hello" } | Out-Null
Try-Request "search.news" "POST" "$base/api/search/news" @{ query = "hello" } | Out-Null

Try-Request "summary.list" "GET" "$base/api/summary/list" | Out-Null

Try-Request "memory.list" "GET" "$base/api/memory/list" | Out-Null
Try-Request "memory.search" "POST" "$base/api/memory/search" @{ query = "hello" } | Out-Null

Try-Request "functions.list" "GET" "$base/api/functions/list" | Out-Null

Try-Request "api_key.list" "GET" "$base/api/api-key/list" | Out-Null

try {
  $tnc = Test-NetConnection -ComputerName 127.0.0.1 -Port 5005 -WarningAction SilentlyContinue
  if ($tnc.TcpTestSucceeded) { Add-Result "voice.ws.port" $true "port open" } else { Add-Result "voice.ws.port" $false "port closed" }
} catch { Add-Result "voice.ws.port" $false ($_.Exception.Message) }

$payload = [PSCustomObject]@{ count = $script:results.Count; results = $script:results }
$payload | ConvertTo-Json -Depth 6 | Set-Content -Path test_results.json -Encoding UTF8
