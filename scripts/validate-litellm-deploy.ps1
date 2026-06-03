# T2.1 - validate LiteLLM compose deploy; optional chat if llama-server is up
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Test-LlamaHost {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:8080/v1/models" -TimeoutSec 5 -UseBasicParsing
        return $true
    } catch {
        return $false
    }
}

function Test-ChatCompletion {
    $key = docker exec newchat-litellm printenv LITELLM_MASTER_KEY
    if (-not $key) { throw "LITELLM_MASTER_KEY not set in container" }
    $jsonPath = Join-Path $env:TEMP "newchat-litellm-test.json"
    [System.IO.File]::WriteAllText(
        $jsonPath,
        '{"model":"newchat","messages":[{"role":"user","content":"Responda apenas: ok"}],"max_tokens":16,"stream":false}'
    )
    $resp = curl.exe -s -w "`n%{http_code}" http://localhost:4000/v1/chat/completions `
        -H "Content-Type: application/json" `
        -H "Authorization: Bearer $key" `
        -d "@$jsonPath"
    $lines = $resp -split "`n"
    $code = $lines[-1]
    $body = ($lines[0..($lines.Length - 2)] -join "`n")
    if ($code -ne "200") {
        Write-Host "FAIL chat completion HTTP $code"
        Write-Host $body
        return $false
    }
    $preview = $body.Substring(0, [Math]::Min(200, $body.Length))
    Write-Host "OK chat completion: $preview..."
    return $true
}

Write-Host "==> docker compose config"
docker compose config | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> docker compose up -d litellm"
docker compose up -d litellm
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$deadline = (Get-Date).AddMinutes(3)
do {
    Start-Sleep -Seconds 5
    $status = docker inspect -f "{{.State.Health.Status}}" newchat-litellm 2>$null
    Write-Host "    health: $status"
    if ($status -eq "healthy") { break }
} while ((Get-Date) -lt $deadline)

if ($status -ne "healthy") {
    Write-Host "FAIL: litellm not healthy within 3m"
    docker compose logs --tail=40 litellm
    exit 1
}

Write-Host "==> GET /health/liveliness"
curl.exe -sf "http://localhost:4000/health/liveliness" | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "OK: LiteLLM deploy config loaded"

if (Test-LlamaHost) {
    Write-Host "==> llama-server up - chat completion test"
    if (-not (Test-ChatCompletion)) { exit 1 }
} else {
    Write-Host "SKIP chat completion (llama-server offline on :8080)"
    Write-Host "      Start: scripts\Server_Qwen3.6-35B.bat or scripts\start-llama-background.ps1"
}
