# Start llama-server in background - same flags as Server_Qwen3.6-35B.bat
$ErrorActionPreference = "Stop"

if (Get-Process llama-server -ErrorAction SilentlyContinue) {
    Write-Host "llama-server already running"
    exit 0
}

$pathsFile = Join-Path $PSScriptRoot "llama-paths.local.bat"
if (-not (Test-Path $pathsFile)) {
    Write-Error "Missing $pathsFile — copy scripts\llama-paths.local.bat.example and set paths."
}

function Get-LlamaPathFromBat {
    param([string]$Name)
    $value = cmd /c "call `"$pathsFile`" >nul 2>&1 && echo %$Name%"
    return ($value | Select-Object -Last 1).Trim()
}

$llamaDir = Get-LlamaPathFromBat "LLAMA_DIR"
$modelPath = Get-LlamaPathFromBat "MODEL_PATH"
$mmprojPath = Get-LlamaPathFromBat "MMPROJ_PATH"

if (-not $llamaDir -or -not $modelPath -or -not $mmprojPath) {
    Write-Error "LLAMA_DIR, MODEL_PATH and MMPROJ_PATH must be set in llama-paths.local.bat"
}

$threads = (Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum
if (-not $threads) { $threads = 8 }

if (-not (Test-Path "$llamaDir\llama-server.exe")) {
    Write-Error "llama-server.exe nao encontrado: $llamaDir"
}
if (-not (Test-Path $modelPath)) { Write-Error "Modelo nao encontrado: $modelPath" }
if (-not (Test-Path $mmprojPath)) { Write-Error "mmproj nao encontrado: $mmprojPath" }

# Single command-line string so paths with spaces are not split (Start-Process array quirk on Windows)
$llamaArgLine = @(
    "-m `"$modelPath`"",
    "--mmproj `"$mmprojPath`"",
    "--image-min-tokens 1024",
    "--no-mmproj-offload",
    "--n-cpu-moe 0 --split-mode row",
    "--no-mmap --mlock",
    "--cache-ram 0",
    "--cache-type-k q8_0 --cache-type-v turbo3",
    "-c 131072 --flash-attn on --cont-batching",
    "--fit on --fit-target 1536",
    "--rope-scaling yarn --rope-scale 4 --yarn-orig-ctx 32768",
    "-t $threads -tb $threads -b 2048 -ub 512",
    "-np 1 --kv-unified",
    "--host 0.0.0.0 --port 8080"
) -join " "

$logDir = Join-Path (Split-Path -Parent $PSScriptRoot) "scripts"
$stdout = Join-Path $logDir "llama-server.out.log"
$stderr = Join-Path $logDir "llama-server.err.log"

Write-Host "Starting llama-server (log: $stderr)..."
Start-Process -FilePath "$llamaDir\llama-server.exe" `
    -WorkingDirectory $llamaDir `
    -ArgumentList $llamaArgLine `
    -WindowStyle Minimized `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr

Write-Host "Aguardando http://127.0.0.1:8080/v1/models ..."
$deadline = (Get-Date).AddMinutes(10)
while ((Get-Date) -lt $deadline) {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:8080/v1/models" -TimeoutSec 5 -UseBasicParsing
        Write-Host "llama-server pronto"
        exit 0
    } catch {
        if (-not (Get-Process llama-server -ErrorAction SilentlyContinue)) {
            Write-Host "llama-server exited - stderr tail:"
            Get-Content $stderr -Tail 20 -ErrorAction SilentlyContinue
            exit 1
        }
        Start-Sleep -Seconds 10
    }
}
Write-Error "Timeout waiting for llama-server"
exit 1
