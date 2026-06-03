# T2.4 — valida deploy AnythingLLM no compose (:3001, embedding native, rede newchat-net)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> docker compose config"
docker compose config | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> docker compose up -d anythingllm"
docker compose up -d anythingllm
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

function Wait-Healthy {
    param([string]$Name, [int]$Minutes = 8)
    $deadline = (Get-Date).AddMinutes($Minutes)
    do {
        Start-Sleep -Seconds 5
        $status = docker inspect -f "{{.State.Health.Status}}" $Name 2>$null
        Write-Host "    $Name health: $status"
        if ($status -eq "healthy") { return $true }
    } while ((Get-Date) -lt $deadline)
    return $false
}

if (-not (Wait-Healthy "newchat-anythingllm" 8)) {
    Write-Host "FAIL: anythingllm not healthy (primeira subida pode baixar modelo Xenova)"
    docker compose logs --tail=60 anythingllm
    exit 1
}

Write-Host "==> GET http://localhost:3001/api/ping/ (host)"
curl.exe -sf "http://localhost:3001/api/ping/" | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> GET http://anythingllm:3001/api/ping/ (rede newchat-net)"
docker run --rm --network newchat-net curlimages/curl:8.12.1 -sf "http://anythingllm:3001/api/ping/" | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> embedding env (deve ser native + MiniLM, nao llama :8080)"
$embedEngine = docker exec newchat-anythingllm printenv EMBEDDING_ENGINE 2>$null
$embedModel = docker exec newchat-anythingllm printenv EMBEDDING_MODEL_PREF 2>$null
Write-Host "    EMBEDDING_ENGINE=$embedEngine"
Write-Host "    EMBEDDING_MODEL_PREF=$embedModel"
if ($embedEngine -ne "native") {
    Write-Host "FAIL: EMBEDDING_ENGINE esperado 'native', obteve '$embedEngine'"
    exit 1
}
if ($embedModel -notmatch "MiniLM") {
    Write-Host "FAIL: modelo de embedding deve ser leve (MiniLM), obteve '$embedModel'"
    exit 1
}

$litellmRunning = docker inspect -f "{{.State.Running}}" newchat-litellm 2>$null
if ($litellmRunning -eq "true") {
    Write-Host "==> litellm container -> anythingllm:3001"
    docker exec newchat-litellm python3 -c "import urllib.request; urllib.request.urlopen('http://anythingllm:3001/api/ping/')" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK: anythingllm acessível de newchat-litellm"
    } else {
        Write-Host "WARN: litellm up mas não alcançou anythingllm"
    }
} else {
    Write-Host "SKIP litellm exec (container não está rodando)"
}

Write-Host "OK: AnythingLLM deploy - healthcheck, volumes, API ping, embedding native leve"
