#!/usr/bin/env pwsh
# Sends a chat completion to LiteLLM with a body from $BodyFile
param(
    [Parameter(Mandatory=$true)][string]$BodyFile,
    [string]$Url = "http://localhost:4000/v1/chat/completions",
    [string]$Key = "minha-litellm-key",
    [string]$UserId = ""
)
if (-not (Test-Path $BodyFile)) { Write-Error "File not found: $BodyFile"; exit 1 }
$body = Get-Content -Raw $BodyFile
$hdrs = @{ "Authorization" = "Bearer $Key"; "Content-Type" = "application/json" }
if ($UserId) { $hdrs["X-User-Id"] = $UserId }
try {
    $resp = Invoke-RestMethod -Uri $Url -Method Post -Headers $hdrs -Body $body -TimeoutSec 600
    $resp | ConvertTo-Json -Depth 10
} catch {
    Write-Host "HTTP ERROR: $($_.Exception.Response.StatusCode.value__)"
    $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
    Write-Host $reader.ReadToEnd()
}
