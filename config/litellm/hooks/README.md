# hooks/

Adaptadores finos entre LiteLLM Proxy e `orchestration/`.

| Módulo | Responsabilidade |
|--------|------------------|
| `request_headers.py` | Extrai headers de `proxy_server_request` / `metadata` |
| `observability.py` | Logs JSON (`request_id`, `user_id`, latência mem0/rag) — T8.2 |
| `llama_fallback.py` | Mensagem HTTP 503 quando llama-server offline — T8.2 |
| `pre_call.py` | Valida `X-User-Id`; mem0 + RAG condicional + context_builder |
| `post_call.py` | Pós-inferência + persistência mem0 |

Hooks **não** importam `litellm` — registro em `custom_callbacks.py`.

Ver [orchestration/README.md](../orchestration/README.md) e [README raiz](../../../README.md).
