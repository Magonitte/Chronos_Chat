# LiteLLM — hub de orquestração

LiteLLM é o **cérebro operacional** do New_Chat: orquestra mem0, RAG e inferência.

**Status:** deploy T2.1 — proxy ativo; callbacks/orchestration em F4+.

## Layout (volume Docker)

Montagem: `./config/litellm` → `/app/config` (read-only)

| Caminho no container | Arquivo | Fase |
|----------------------|---------|------|
| `/app/config/config.yaml` | Routing → llama.cpp | T1.1 / T2.1 |
| `/app/config/custom_callbacks.py` | Registro de hooks | F4.5 |
| `/app/config/orchestration/` | Lógica pura (sem `import litellm`) | F4+ |
| `/app/config/hooks/` | `pre_call`, `post_call` | F4.5 |

`PYTHONPATH=/app/config` permite `import orchestration.*` e `import custom_callbacks` dentro do container.

## Variáveis de ambiente

Definidas no `.env` da raiz (ver `.env.example` e `config/litellm/.env.example`).

| Variável | Uso |
|----------|-----|
| `LITELLM_MASTER_KEY` | Auth do proxy |
| `LLAMA_API_BASE` | Inferência (host `host.docker.internal:8080`) |
| `MEM0_API_URL` | Cliente mem0 (F5) |
| `ANYTHINGLLM_API_URL` | Cliente RAG (F6) |
| `ALLOWED_USER_IDS` | Allowlist `jean`, `tati` (F4) |
| `CTX_*` | Context budget 131k (F4) |

## Validar deploy (T2.1)

Na raiz do repositório:

```powershell
docker compose config
docker compose restart litellm
# aguardar healthy (~60s start_period)
curl.exe -sf http://localhost:4000/health/liveliness
```

Ou script:

```powershell
.\scripts\validate-litellm-deploy.ps1
```

Chat completion (requer llama-server no host):

```powershell
$key = docker exec newchat-litellm printenv LITELLM_MASTER_KEY
$body = '{"model":"newchat","messages":[{"role":"user","content":"ok"}],"max_tokens":8,"stream":false}'
curl.exe -s http://localhost:4000/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $key" `
  -d $body
```

## Documentação

- [README](../../README.md) — arquitetura e operação
- [orchestration/README.md](orchestration/README.md) — módulos do hub
- [hooks/README.md](hooks/README.md) — pre_call / post_call
