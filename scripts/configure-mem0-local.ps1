# Configura mem0 para LLM :8080 (Qwen chat) + embedder :8081 (Qwen3-Embedding)
$ErrorActionPreference = "Stop"

$EmbedModel = "qwen3-embedding-0.6b"
$ChatModel = "Qwen3.6-35B-A3B-uncensored-heretic-APEX-I-Mini.gguf"
$Mem0Url = "http://localhost:8000"

Write-Host "==> Teste embedder :8081"
try {
    $emb = Invoke-RestMethod -Uri "http://127.0.0.1:8081/v1/embeddings" -Method Post `
        -ContentType "application/json" `
        -Body (@{ model = $EmbedModel; input = "Eu gosto de chocolate amargo" } | ConvertTo-Json) `
        -TimeoutSec 30
    $dim = $emb.data[0].embedding.Count
    Write-Host "    OK - embedding dim=$dim"
} catch {
    Write-Host "FAIL: embedder :8081 - suba scripts\Server_Qwen3-Embedding-0.6B.bat"
    Write-Host $_.Exception.Message
    exit 1
}

Write-Host "==> POST $Mem0Url/configure"
$config = @{
    llm = @{
        provider = "openai"
        config = @{
            api_key         = "none"
            openai_base_url = "http://host.docker.internal:8080/v1"
            model           = $ChatModel
            temperature     = 0
            max_tokens      = 1024
        }
    }
    embedder = @{
        provider = "openai"
        config = @{
            api_key         = "none"
            openai_base_url = "http://host.docker.internal:8081/v1"
            model           = $EmbedModel
        }
    }
    vector_store = @{
        config = @{
            embedding_model_dims = $dim
        }
    }
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Uri "$Mem0Url/configure" -Method Post -ContentType "application/json" -Body $config | Out-Null

Write-Host "==> Recriar tabela pgvector com dims=$dim (drop + restart mem0)"
docker exec newchat-mem0-postgres psql -U mem0 -d mem0 -c "DROP TABLE IF EXISTS memories CASCADE;" | Out-Null
docker restart newchat-mem0 | Out-Null
$deadline = (Get-Date).AddMinutes(2)
do {
    Start-Sleep -Seconds 3
    $status = docker inspect -f "{{.State.Health.Status}}" newchat-mem0 2>$null
} while ((Get-Date) -lt $deadline -and $status -ne "healthy")
if ($status -ne "healthy") {
    Write-Host "FAIL: mem0 nao ficou healthy apos restart"
    exit 1
}
Invoke-RestMethod -Uri "$Mem0Url/configure" -Method Post -ContentType "application/json" -Body $config | Out-Null

Write-Host "==> Teste mem0 search"
$searchBody = '{"query":"chocolate","user_id":"jean"}'
try {
    $search = Invoke-RestMethod -Uri "$Mem0Url/search" -Method Post -ContentType "application/json" -Body $searchBody
    $count = 0
    if ($search.results) { $count = $search.results.Count }
    Write-Host "    OK - search respondeu (results=$count)"
} catch {
    if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
    Write-Host "WARN: search falhou (pgvector dims antigas? veja nota abaixo)"
}

Write-Host ""
Write-Host "OK: mem0 configurado (LLM :8080, embedder :8081, dims=$dim)"
Write-Host "Se erro de dimensao no pgvector:"
Write-Host "  docker compose stop mem0 mem0-postgres"
Write-Host "  docker volume rm newchat_mem0_postgres_data"
Write-Host "  docker compose up -d mem0-postgres mem0"
Write-Host "  .\scripts\configure-mem0-local.ps1"
