# AGENTS.md — Chronos Chat

Guia para agentes de IA que trabalham neste repositório.

## O que é este projeto

IA pessoal auto-hospedada para dois usuários (`jean`, `tati`): UI estilo ChatGPT, memória de longo prazo (mem0), RAG em documentos (AnythingLLM), visão e MCP de ações no futuro. **Sem inferência na nuvem.**

## Arquitetura

```
Usuário → LibreChat (UI fina)
              ↓
         LiteLLM (HUB)
              ↓
   ┌──────┼──────┐
   ↓      ↓      ↓
 mem0  AnythingLLM  llama.cpp (host :8080)
```

- **LibreChat** fala **somente** com o LiteLLM.
- **LiteLLM** orquestra via `config/litellm/orchestration/` e hooks finos em `config/litellm/hooks/`.
- **MCP (fase 3):** só ações — não memória/RAG base.

## O que roda onde

| Componente | Ambiente | Como iniciar |
|------------|----------|--------------|
| llama-server | Host Windows | `scripts/Server_Qwen3.6-35B.bat` (+ `llama-paths.local.bat`) |
| LiteLLM, LibreChat, mem0, AnythingLLM | Docker | `docker compose up -d` / `scripts/start-stack.bat` |

## Layout do repositório

```
config/
  litellm/
    orchestration/   # Python puro — PROIBIDO import litellm
    hooks/           # pre_call, post_call — fronteira LiteLLM
  librechat/
  mem0/
  anythingllm/
scripts/
tests/
```

Leia [README.md](README.md) para instalação e execução. Por serviço: `config/*/README.md`.

## Ordem de implementação (histórico)

1. docker-compose + LiteLLM → llama.cpp  
2. LibreChat → somente LiteLLM (sem plugins nativos de RAG/memória)  
3. Esqueleto orchestration + hooks  
4. mem0 PRE/POST + `memory_policy`  
5. RAG `rag_policy` + `rag_client`  
6. Observabilidade  
7. **F10** `thinking_policy` + `apply_thinking` (reasoning por contexto)  
8. MCP ações (fase 3)

## Restrições críticas

- **Nunca** alterar flags do llama-server em `scripts/Server_Qwen3.6-35B.bat` sem aprovação explícita e revalidação.
- **Nunca** LibreChat → mem0/AnythingLLM direto.
- **Nunca** callbacks monolíticos — usar `orchestration/` + policies.
- **Nunca** RAG por keyword solta — usar `rag_policy.should_trigger`.
- **Nunca** thinking sempre ligado — usar `thinking_policy.should_enable` no PRE-CALL.
- **Nunca** `import litellm` em `orchestration/`.
- **Nunca** fallback de `user_id` — exigir header `X-User-Id`.
- Memória isolada por `user_id` (`jean` / `tati`).
- Context budget: ver `CTX_*` em `.env.example` e `orchestration/context_budget.py`.

## Ao implementar

- Uma mudança focada por tarefa.
- Adicionar testes para policies e `context_builder`.
- Não commitar `.env`, `docs/`, `.cursor/` nem `llama-paths.local.bat`.
