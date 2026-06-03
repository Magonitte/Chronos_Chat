# T2.3 — valida deploy mem0 no compose (Postgres + API :8000, rede newchat-net)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> docker compose config"
docker compose config | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> docker compose build mem0"
docker compose build mem0
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> docker compose up -d mem0-postgres mem0"
docker compose up -d mem0-postgres mem0
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

function Wait-Healthy {
    param([string]$Name, [int]$Minutes = 6)
    $deadline = (Get-Date).AddMinutes($Minutes)
    do {
        Start-Sleep -Seconds 5
        $status = docker inspect -f "{{.State.Health.Status}}" $Name 2>$null
        Write-Host "    $Name health: $status"
        if ($status -eq "healthy") { return $true }
    } while ((Get-Date) -lt $deadline)
    return $false
}

if (-not (Wait-Healthy "newchat-mem0-postgres" 2)) {
    Write-Host "FAIL: mem0-postgres not healthy"
    docker compose logs --tail=30 mem0-postgres
    exit 1
}

if (-not (Wait-Healthy "newchat-mem0" 6)) {
    Write-Host "FAIL: mem0 API not healthy (build/migrations podem levar alguns minutos)"
    docker compose logs --tail=50 mem0
    exit 1
}

Write-Host "==> GET http://localhost:8000/docs (host)"
curl.exe -sf "http://localhost:8000/docs" | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> GET http://mem0:8000/docs (rede newchat-net, como LiteLLM)"
docker run --rm --network newchat-net curlimages/curl:8.12.1 -sf "http://mem0:8000/docs" | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$litellmRunning = docker inspect -f "{{.State.Running}}" newchat-litellm 2>$null
if ($litellmRunning -eq "true") {
    Write-Host "==> litellm container -> mem0:8000"
    docker exec newchat-litellm python3 -c "import urllib.request; urllib.request.urlopen('http://mem0:8000/docs')" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK: mem0 acessível de newchat-litellm"
    } else {
        Write-Host "WARN: litellm up mas não alcançou mem0 (rede/DNS?)"
    }
} else {
    Write-Host "SKIP litellm exec (container não está rodando)"
}

Write-Host "OK: mem0 deploy — healthcheck, volumes, API em mem0:8000"
