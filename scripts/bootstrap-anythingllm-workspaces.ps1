# Cria workspaces jean/tati via API AnythingLLM (após onboarding + API key no .env)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Get-EnvValue {
    param([string]$Key)
    if (Test-Path ".env") {
        $line = Get-Content ".env" | Where-Object { $_ -match "^\s*$Key\s*=" } | Select-Object -First 1
        if ($line) {
            return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
        }
    }
    return (Get-Item -Path "Env:$Key" -ErrorAction SilentlyContinue).Value
}

$apiKey = Get-EnvValue "ANYTHINGLLM_API_KEY"
if (-not $apiKey -or $apiKey -match "change-me") {
    Write-Host "Defina ANYTHINGLLM_API_KEY no .env (Settings -> API Keys na UI AnythingLLM)."
    exit 1
}

$baseUrl = Get-EnvValue "ANYTHINGLLM_API_URL"
if (-not $baseUrl) { $baseUrl = "http://localhost:3001" }
# Script roda no host — usar localhost se URL for interna do compose
if ($baseUrl -match "anythingllm:3001") { $baseUrl = "http://localhost:3001" }

$headers = @{
    Authorization = "Bearer $apiKey"
    "Content-Type" = "application/json"
}

$workspaces = @(
    @{ name = "Jean Carlos de Souza"; slug = "jean" }
    @{ name = "Tatiane Schlüter de Souza"; slug = "tatiane-schluter-de-souza" }
)

foreach ($ws in $workspaces) {
    $body = @{ name = $ws.name; slug = $ws.slug } | ConvertTo-Json
    try {
        $resp = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/workspace/new" -Headers $headers -Body $body
        $actualSlug = $resp.workspace.slug
        Write-Host "OK: workspace criado id=$($resp.workspace.id) slug=$actualSlug name=$($resp.workspace.name)"
    } catch {
        $status = $_.Exception.Response.StatusCode.value__
        if ($status -eq 409 -or $_.ErrorDetails.Message -match "already exists") {
            Write-Host "SKIP: workspace '$($ws.slug)' já existe"
        } else {
            Write-Host "FAIL: workspace '$($ws.slug)' - $($_.Exception.Message)"
            if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
            exit 1
        }
    }
}

Write-Host "OK: workspaces jean/tati prontos (ver config/anythingllm/workspaces.yaml)"
