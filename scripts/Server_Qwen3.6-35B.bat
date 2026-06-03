@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%llama-paths.local.bat" (
    call "%SCRIPT_DIR%llama-paths.local.bat"
) else (
    echo [ERRO] Arquivo ausente: scripts\llama-paths.local.bat
    echo        Copie scripts\llama-paths.local.bat.example e configure LLAMA_DIR / MODEL_PATH / MMPROJ_PATH.
    pause
    exit /b 1
)

if not defined LLAMA_DIR (
    echo [ERRO] LLAMA_DIR nao definido em llama-paths.local.bat
    pause
    exit /b 1
)
if not defined MODEL_PATH (
    echo [ERRO] MODEL_PATH nao definido em llama-paths.local.bat
    pause
    exit /b 1
)
if not defined MMPROJ_PATH (
    echo [ERRO] MMPROJ_PATH nao definido em llama-paths.local.bat
    pause
    exit /b 1
)

echo [Limpeza] Encerrando processos anteriores...
taskkill /f /im mcpo.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
echo [Limpeza] Encerrando llama-server na porta 8080 (embedder :8081 permanece)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8080 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
timeout /t 2 /nobreak > nul

set CTX_SIZE=131072
set FIT_TARGET_MB=1536
set BATCH_SIZE=2048
set UBATCH_SIZE=512

for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum"`) do set "THREADS=%%i"
if not defined THREADS set "THREADS=8"
set CPU_MOE=0

cd /d "%LLAMA_DIR%"

if not exist llama-server.exe (
    echo [ERRO] llama-server.exe nao encontrado em: %LLAMA_DIR%
    pause
    exit /b 1
)

if not exist "%MODEL_PATH%" (
    echo [ERRO] Modelo nao encontrado: %MODEL_PATH%
    pause
    exit /b 1
)

if not exist "%MMPROJ_PATH%" (
    echo [ERRO] mmproj nao encontrado: %MMPROJ_PATH%
    pause
    exit /b 1
)

echo [TurboQuant] Qwen3.6-35B-A3B APEX-I-Mini + VISAO
echo   mmproj: %MMPROJ_PATH%
echo   image-min-tokens=1024 ctx=%CTX_SIZE% fit-target=%FIT_TARGET_MB% MiB
echo   Acesso na rede: porta 8080 (mesma Wi-Fi/LAN)
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do echo     http://%%a:8080
echo   So neste PC: http://127.0.0.1:8080
echo   Firewall: libere TCP 8080 se outro dispositivo nao conectar
echo.


.\llama-server.exe -m "%MODEL_PATH%" ^
  --mmproj "%MMPROJ_PATH%" ^
  --image-min-tokens 1024 ^
  --no-mmproj-offload ^
  --n-cpu-moe %CPU_MOE% --split-mode row ^
  --no-mmap --mlock ^
  --cache-ram 2048 ^
  --cache-type-k q8_0 --cache-type-v turbo3 ^
  -c %CTX_SIZE% --flash-attn on --cont-batching ^
  --fit on --fit-target %FIT_TARGET_MB% ^
  --rope-scaling yarn --rope-scale 4 --yarn-orig-ctx 32768 ^
  -t %THREADS% -tb %THREADS% -b %BATCH_SIZE% -ub %UBATCH_SIZE% ^
  -np 1 --kv-unified ^
  --host 0.0.0.0 --port 8080

pause
endlocal
