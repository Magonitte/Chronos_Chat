# mem0 — serviço de memória episódica

Deploy do serviço mem0. A **lógica** de quando buscar/salvar fica no LiteLLM (`config/litellm/orchestration/`).

## Arquivos

| Arquivo | Função |
|---------|--------|
| `Dockerfile` | Build amd64 da API (`mem0ai/mem0` → `server/`) |
| `docker-entrypoint.sh` | Aguarda Postgres, migrações Alembic, `uvicorn :8000` |
| `init-db.sh` | Init do Postgres: cria `MEM0_APP_DB_NAME` (auth) |
| `.env.example` | Referência de variáveis (valores reais no `.env` da raiz) |

## Docker (amd64 / Windows)

A imagem `mem0/mem0-api-server` no Hub é **somente linux/arm64**. O compose usa **build local** (`newchat-mem0-api:local`).

**Persistência**

- `mem0_postgres_data` — vetores + metadados (pgvector)
- `mem0_history_data` — SQLite de histórico (`HISTORY_DB_PATH`)

**Rede**

- Serviço: `mem0` → `http://mem0:8000` em `newchat-net`
- LiteLLM: `MEM0_API_URL=http://mem0:8000` (já no `docker-compose.yml`)

## Subir e validar

```powershell
# Na raiz do repo (primeira vez: build pode levar vários minutos)
docker compose build mem0
docker compose up -d mem0-postgres mem0

# Validação automatizada (T2.3)
.\scripts\validate-mem0-deploy.ps1
```

Critérios: healthcheck `healthy`, `curl http://localhost:8000/docs`, acesso por hostname `mem0` na rede interna.

## Variáveis (raiz `.env`)

Ver `.env.example` na raiz e `config/mem0/.env.example`. Em dev local: `MEM0_AUTH_DISABLED=true`, `MEM0_JWT_SECRET` definido.

## Regras

- Isolamento por `user_id`: `jean`, `tati` (contrato no LiteLLM, fase F5)
- Acessado **somente** pela rede interna — LiteLLM → `mem0:8000`
- LibreChat **não** chama mem0 diretamente

Fluxo: PRE-CALL `mem0_client.search`, POST-CALL `memory_policy` + `mem0_client.add`. Ver [README](../../README.md).
