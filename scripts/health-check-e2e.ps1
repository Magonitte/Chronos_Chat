# T3.1 — chat completion smoke: LiteLLM :4000 -> llama.cpp :8080
$ErrorActionPreference = "Stop"

function Get-MasterKey {
    $fromDocker = docker exec newchat-litellm printenv LITELLM_MASTER_KEY 2>$null
    if ($fromDocker) { return $fromDocker.Trim() }
    $envFile = Join-Path (Split-Path -Parent $PSScriptRoot) ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*LITELLM_MASTER_KEY\s*=\s*(.+)\s*$') {
                return $Matches[1].Trim().Trim('"').Trim("'")
            }
        }
    }
    throw "LITELLM_MASTER_KEY not found (.env or container)"
}

$key = Get-MasterKey
$jsonPath = Join-Path $env:TEMP "newchat-smoke-e2e.json"
[System.IO.File]::WriteAllText(
    $jsonPath,
    '{"model":"newchat","messages":[{"role":"user","content":"Responda apenas: ok"}],"max_tokens":32,"stream":false}'
)

$resp = curl.exe -s -w "`n%{http_code}" "http://localhost:4000/v1/chat/completions" `
    -H "Content-Type: application/json" `
    -H "Authorization: Bearer $key" `
    -H "X-User-Id: jean" `
    -d "@$jsonPath"

$lines = $resp -split "`n"
$code = $lines[-1]
$body = ($lines[0..($lines.Length - 2)] -join "`n")

if ($code -ne "200") {
    Write-Host "HTTP $code"
    if ($body) { Write-Host $body.Substring(0, [Math]::Min(500, $body.Length)) }
    exit 1
}

if ($body -notmatch 'choices') {
    Write-Host "Resposta sem choices: $($body.Substring(0, [Math]::Min(200, $body.Length)))"
    exit 1
}

exit 0
