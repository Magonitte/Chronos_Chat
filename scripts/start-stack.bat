@echo off
setlocal EnableExtensions
REM T3.1 — sobe a stack Docker Chronos_Chat (llama.cpp fica FORA do compose).
REM Pre-requisito recomendado: scripts\Server_Qwen3.6-35B.bat (host :8080)

cd /d "%~dp0.."
set "ROOT=%CD%"

echo.
echo === Chronos_Chat: start-stack (T3.1) ===
echo Repo: %ROOT%
echo.

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Docker CLI nao encontrado. Inicie o Docker Desktop.
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Docker nao esta respondendo. Abra o Docker Desktop e tente de novo.
    exit /b 1
)

if not exist "%ROOT%\.env" (
    echo [ERRO] Arquivo .env ausente. Copie de .env.example:
    echo        copy .env.example .env
    exit /b 1
)

echo [1/3] docker compose config ...
docker compose config >nul
if errorlevel 1 (
    echo [ERRO] docker compose config falhou.
    exit /b 1
)

echo [2/3] docker compose up -d ...
docker compose up -d
if errorlevel 1 (
    echo [ERRO] docker compose up -d falhou.
    exit /b 1
)

echo.
echo [3/3] Aguardando healthchecks (pode levar varios minutos na 1a vez; mem0 build) ...
echo       Dica: em outro terminal, suba o llama antes do chat:
echo       scripts\Server_Qwen3.6-35B.bat
echo.

call "%~dp0health-check.bat" --wait
set "HC=%ERRORLEVEL%"

echo.
if "%HC%"=="0" (
    echo === Stack Docker OK ===
    echo LibreChat:  http://localhost:3080
    echo LiteLLM:    http://localhost:4000
    echo AnythingLLM: http://localhost:3001
    echo mem0 API:   http://localhost:8000/docs
    echo.
    curl.exe -sf --max-time 5 "http://127.0.0.1:8080/v1/models" >nul 2>&1
    if errorlevel 1 (
        echo Proximo passo: scripts\Server_Qwen3.6-35B.bat
        echo Depois abra: http://localhost:3080
    ) else (
        echo Pronto para chat: http://localhost:3080
        echo Modelo NewChat / contas jean ou tati — E2E LiteLLM-^>llama OK no health-check.
    )
) else (
    echo === Stack com falhas no health-check ===
    echo Ver: docker compose ps
    echo      docker compose logs --tail=50 ^<servico^>
)

exit /b %HC%
