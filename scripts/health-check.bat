@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM T3.1 — health HTTP + Docker para LiteLLM, LibreChat, mem0, AnythingLLM; hint llama host :8080
REM Uso: health-check.bat          (checagem rapida)
REM      health-check.bat --wait   (aguarda containers healthy, ate ~8 min)

cd /d "%~dp0.."
set "FAIL=0"
set "WAIT=0"
set "LLAMA_UP=0"
if /i "%~1"=="--wait" set "WAIT=1"

echo.
echo === Chronos_Chat health-check (T3.1) ===
echo.

if "%WAIT%"=="1" call :wait_containers

call :check_llama_hint

call :check_http "LiteLLM" "http://localhost:4000/health/liveliness" "newchat-litellm"
call :check_http "LibreChat" "http://localhost:3080/" "newchat-librechat"
call :check_http "mem0" "http://localhost:8000/docs" "newchat-mem0"
call :check_http "AnythingLLM" "http://localhost:3001/api/ping/" "newchat-anythingllm"

call :check_chat_e2e

echo.
if "%FAIL%"=="0" (
    echo === RESULTADO: OK - servicos Docker ===
) else (
    echo === RESULTADO: FALHA - um ou mais servicos ===
    echo docker compose ps
    echo docker compose logs --tail=40 litellm librechat mem0 anythingllm
)

if "%FAIL%"=="0" (
    endlocal
    exit /b 0
)
endlocal
exit /b 1

:wait_containers
echo [wait] Aguardando containers healthy ...
powershell -NoProfile -Command ^
  "$names=@('newchat-litellm','newchat-mongodb','newchat-meilisearch','newchat-mem0-postgres','newchat-mem0','newchat-anythingllm','newchat-librechat');" ^
  "$deadline=(Get-Date).AddMinutes(8);" ^
  "do {" ^
  "  Start-Sleep -Seconds 8;" ^
  "  $bad=@();" ^
  "  foreach($n in $names){" ^
  "    $s=docker inspect -f '{{.State.Health.Status}}' $n 2>$null;" ^
  "    if(-not $s){$s='missing'};" ^
  "    Write-Host ('    {0,-28} {1}' -f $n,$s);" ^
  "    if($s -ne 'healthy'){$bad+=$n}" ^
  "  };" ^
  "  if($bad.Count -eq 0){Write-Host '[wait] Todos healthy.'; exit 0}" ^
  "} while((Get-Date) -lt $deadline);" ^
  "Write-Host '[wait] Timeout — alguns servicos ainda nao healthy (mem0 pode levar mais).'; exit 0"
echo.
goto :eof

:check_llama_hint
curl.exe -sf --max-time 5 "http://127.0.0.1:8080/v1/models" >nul 2>&1
if errorlevel 1 (
    echo [HINT] llama-server OFFLINE em http://127.0.0.1:8080
    echo        Chat no LibreChat falha ate subir: scripts\Server_Qwen3.6-35B.bat
    echo        Ou: scripts\start-llama-background.ps1
    set "LLAMA_UP=0"
) else (
    echo [OK]   llama-server host :8080 /v1/models
    set "LLAMA_UP=1"
)
echo.
goto :eof

:check_http
set "LABEL=%~1"
set "URL=%~2"
set "CNAME=%~3"
set "HTTP_OK=0"

curl.exe -sf --max-time 15 "%URL%" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] %LABEL% HTTP %URL%
    set "FAIL=1"
) else (
    echo [OK]   %LABEL% HTTP %URL%
    set "HTTP_OK=1"
)

if defined CNAME (
    docker inspect -f "{{.State.Health.Status}}" %CNAME% >nul 2>&1
    if errorlevel 1 (
        echo        container %CNAME%: nao encontrado
        set "FAIL=1"
    ) else (
        for /f "delims=" %%s in ('docker inspect -f "{{.State.Health.Status}}" %CNAME% 2^>nul') do set "DHC=%%s"
        if /i "!DHC!"=="healthy" (
            echo        container %CNAME%: healthy
        ) else (
            echo        container %CNAME%: !DHC! ^(aguarde: health-check.bat --wait^)
            set "FAIL=1"
        )
    )
)
goto :eof

:check_chat_e2e
if not "!LLAMA_UP!"=="1" (
    echo [SKIP] chat E2E LiteLLM-^>llama ^(llama offline^)
    echo.
    goto :eof
)

echo [E2E] chat completion LiteLLM -^> llama.cpp ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0health-check-e2e.ps1"
if errorlevel 1 (
    echo [FAIL] chat E2E via LiteLLM
    set "FAIL=1"
) else (
    echo [OK]   chat E2E LiteLLM -^> llama.cpp
)
echo.
goto :eof
