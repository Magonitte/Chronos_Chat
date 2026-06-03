# Mapeamento conta LibreChat → X-User-Id

Contrato: o header `X-User-Id` deve estar em `ALLOWED_USER_IDS` no `.env` (fail-closed). Ver [README](../../README.md#arquitetura).

| Conta LibreChat (username) | Header enviado ao LiteLLM |
|----------------------------|---------------------------|
| `jean`                     | `X-User-Id: jean`         |
| `tati`                     | `X-User-Id: tati`         |

## Regras

1. Registrar **somente** com usernames `jean` ou `tati` (minúsculas, sem espaços). Nome de exibição pode ser "Tati".
2. O `librechat.yaml` usa `{{LIBRECHAT_USER_USERNAME}}` no header — qualquer outro username será rejeitado pelo LiteLLM (400) quando os hooks F4.5 estiverem ativos.
3. Não usar memória/RAG nativos do LibreChat; memória e documentos passam pelo hub LiteLLM.

## T7.1 (implementado)

Username da conta LibreChat = `user_id` enviado no header. Mapeamento mínimo: `jean` | `tati`.
