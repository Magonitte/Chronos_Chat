@echo off
setlocal

rem Embedder mem0 — embedding local (porta 8081)
rem Iniciar DEPOIS do Server_Qwen3.6-35B.bat (:8080).
rem O .bat do chat so mata o processo na porta 8080 — este embedder continua ativo.

set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%llama-paths.local.bat" (
    call "%SCRIPT_DIR%llama-paths.local.bat"
) else (
    echo [ERRO] Arquivo ausente: scripts\llama-paths.local.bat
    echo        Copie scripts\llama-paths.local.bat.example e configure LLAMA_DIR / EMBED_MODEL_PATH.
    pause
    exit /b 1
)

if not defined LLAMA_DIR (
    echo [ERRO] LLAMA_DIR nao definido em llama-paths.local.bat
    pause
    exit /b 1
)
if defined EMBED_MODEL_PATH (
    set "MODEL_PATH=%EMBED_MODEL_PATH%"
)
if not defined MODEL_PATH (
    echo [ERRO] EMBED_MODEL_PATH ou MODEL_PATH nao definido em llama-paths.local.bat
    pause
    exit /b 1
)
set "EMBED_PORT=8081"
set "EMBED_CTX=8192"

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

echo [Embedder] Qwen3-Embedding-0.6B Q8_0 — mem0 / RAG embeddings
echo   modelo: %MODEL_PATH%
echo   porta:  %EMBED_PORT%  ^(chat Qwen 35B continua em :8080^)
echo   CPU: -ngl 0 ^(nao compete com GPU do chat^)
echo   teste: curl http://127.0.0.1:%EMBED_PORT%/v1/models
echo.

.\llama-server.exe -m "%MODEL_PATH%" ^
  --embeddings ^
  --pooling last ^
  --alias qwen3-embedding-0.6b ^
  --host 0.0.0.0 ^
  --port %EMBED_PORT% ^
  -ngl 0 ^
  -c %EMBED_CTX% ^
  -b %EMBED_CTX% ^
  -ub %EMBED_CTX% ^
  -np 1

pause
endlocal
