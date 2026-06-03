# LibreChat — UI fina

LibreChat é **somente interface**. Todo fluxo passa pelo LiteLLM.

## Regras

- Backend LLM: **LiteLLM** (`http://litellm:4000/v1`) — único endpoint custom
- `ENDPOINTS=custom` — sem OpenAI/assistants/agents cloud
- **Não** usar RAG/memória nativos do LibreChat (`fileSearch: false`, `memory.disabled: true`)
- Header `X-User-Id` via `librechat.yaml` → `{{LIBRECHAT_USER_USERNAME}}` (contas `jean` | `tati`)
- Mapeamento: [user-mapping.md](user-mapping.md)

## Arquivos

| Arquivo | Função |
|---------|--------|
| `librechat.yaml` | Endpoint NewChat → LiteLLM, headers, UI mínima |
| `.env.example` | Variáveis LibreChat (copiar para `.env` na raiz) |
| `user-mapping.md` | Conta → `X-User-Id` |

## Docker

Montado em `/app/client-config`; `CONFIG_PATH=/app/client-config/librechat.yaml` no compose.

Ver [README](../../README.md).
