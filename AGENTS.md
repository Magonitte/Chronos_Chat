# AGENTS.md — Chronos Chat

Guide for AI coding agents working in this repository.

## What this project is

Self-hosted personal AI for two users (`jean`, `tati`): ChatGPT-style UI, long-term memory (mem0), document RAG (AnythingLLM), vision, future MCP actions. **No cloud inference.**

## Architecture

```
User → LibreChat (thin UI)
          ↓
     LiteLLM (HUB)
          ↓
   ┌──────┼──────┐
   ↓      ↓      ↓
 mem0  AnythingLLM  llama.cpp (host :8080)
```

- **LibreChat** talks **only** to LiteLLM.
- **LiteLLM** orchestrates via `config/litellm/orchestration/` and thin hooks in `config/litellm/hooks/`.
- **MCP (phase 3):** actions only — not base memory/RAG.

## Where things run

| Component | Environment | Start |
|-----------|-------------|--------|
| llama-server | Windows host | `scripts/Server_Qwen3.6-35B.bat` (+ `llama-paths.local.bat`) |
| LiteLLM, LibreChat, mem0, AnythingLLM | Docker | `docker compose up -d` / `scripts/start-stack.bat` |

## Repo layout

```
config/
  litellm/
    orchestration/   # pure Python — NO import litellm
    hooks/           # pre_call, post_call — LiteLLM boundary
  librechat/
  mem0/
  anythingllm/
scripts/
tests/
```

Read [README.md](README.md) for install/run. Per-service: `config/*/README.md`.

## Implementation order (historical)

1. docker-compose + LiteLLM → llama.cpp  
2. LibreChat → LiteLLM only (no native RAG/memory plugins)  
3. orchestration skeleton + hooks  
4. mem0 PRE/POST + `memory_policy`  
5. RAG `rag_policy` + `rag_client`  
6. Observability  
7. MCP actions (phase 3)

## Critical constraints

- **Never** change llama-server flags in `scripts/Server_Qwen3.6-35B.bat` without explicit user approval and revalidation.
- **Never** LibreChat → mem0/AnythingLLM direct calls.
- **Never** monolithic callbacks — use `orchestration/` + policies.
- **Never** keyword-only RAG — use `rag_policy.should_trigger`.
- **Never** `import litellm` in `orchestration/`.
- **Never** `user_id` fallback — require `X-User-Id` header.
- Memory isolated per `user_id` (`jean` / `tati`).
- Context budget: see `CTX_*` in `.env.example` and `orchestration/context_budget.py`.

## When implementing

- One focused change per task.
- Add tests for policies and `context_builder`.
- Do not commit `.env`, `docs/`, `.cursor/`, or `llama-paths.local.bat`.
