# AnythingLLM — RAG e documentos

Deploy do serviço AnythingLLM. Retrieval no chat via LiteLLM `rag_client.py` (F6).

## Arquivos

| Arquivo | Função |
|---------|--------|
| `.env.example` | Referência de variáveis (valores reais no `.env` da raiz) |
| `workspaces.yaml` | Mapeamento `user_id` → workspace slug (`jean`, `tati`) |
| `documents/jean/`, `documents/tati/` | Staging local de PDF/TXT/MD (montado read-only no container) |

## Docker

- Imagem: `mintplexlabs/anythingllm:latest`
- Serviço: `anythingllm` → `http://anythingllm:3001` em `newchat-net`
- Volume: `anythingllm_storage` (DB LanceDB, vetores, cache Xenova)
- Mount: `./config/anythingllm/documents` → `/app/server/storage/import-documents` (ro)

## Embedding (local, leve)

Configurado no `docker-compose.yml` — **não** usa llama.cpp (`:8080`) nem Qwen 35B:

| Variável | Valor padrão |
|----------|----------------|
| `EMBEDDING_ENGINE` | `native` |
| `EMBEDDING_MODEL_PREF` | `Xenova/all-MiniLM-L6-v2` |
| `VECTOR_DB` | `lancedb` |

Roda em CPU dentro do container; não compete com o llama-server por VRAM.

## Workspaces (2 usuários)

| `user_id` | Workspace (nome na UI) | Slug (API) | Pasta de staging |
|-----------|------------------------|------------|------------------|
| `jean` | Jean Carlos de Souza | `jean-carlos-de-souza` | `documents/jean/` |
| `tati` | Tatiane Schlüter de Souza | `tatiane-schluter-de-souza` | `documents/tati/` |

Os slugs são normalizados pelo AnythingLLM a partir do nome; ver `workspaces.yaml`.

**Primeira execução:** AnythingLLM exige onboarding na UI (`http://localhost:3001`). Após concluir:

1. Settings → Embedding: deve mostrar **Native** / `Xenova/all-MiniLM-L6-v2` (já definido por ENV).
2. Criar workspaces com os nomes acima — ou rodar o bootstrap (com API key).
3. Settings → API Keys → gerar chave → copiar para `ANYTHINGLLM_API_KEY` no `.env` da raiz (para `rag_client` em F6).

```powershell
.\scripts\bootstrap-anythingllm-workspaces.ps1
```

## Subir e validar

```powershell
docker compose up -d anythingllm
.\scripts\validate-anythingllm-deploy.ps1
```

Critérios: healthcheck `healthy`, `GET /api/ping/`, acesso por hostname `anythingllm` na rede interna.

## Regras

- LibreChat **não** chama AnythingLLM no fluxo de chat
- LiteLLM aciona via `rag_policy.should_trigger()` + `rag_client` (F6)
- Ingestão: UI AnythingLLM ou API — separada do chat

RAG condicional via `rag_policy` + `rag_client`. Ver [README](../../README.md).
