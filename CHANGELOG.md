# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Planejado

- F9 — MCP para ações (não memória/RAG base)

---

## [1.1.0] - 2026-06-03

Tag: [`v1.1.0`](https://github.com/Magonitte/Chronos_Chat/releases/tag/v1.1.0)

### Adicionado

- **F10 — Pensamento automático por contexto** (`thinking_policy.py`)
  - Reasoning do Qwen ligado só quando o contexto exige (RAG multi-chunk, pergunta complexa, histórico longo, visão + pergunta substantiva)
  - Desligado em saudações triviais, recall de memória, comandos “lembre que…” e requests internos do LibreChat
- `request_tuning.apply_thinking()` — substitui o desligamento global de thinking
- Variáveis `NEWCHAT_THINKING_*` em `.env.example` e `docker-compose.yml`
- Testes em `tests/test_thinking_policy.py`

### Removido

- `NEWCHAT_DISABLE_THINKING` do `docker-compose` (legado; controle via `NEWCHAT_THINKING_ENABLED` + policy)

### Documentação

- README: seção *Pensamento automático (F10)* em PT-BR

---

## [1.0.1] - 2026-06-03

### Alterado

- README, SECURITY e AGENTS traduzidos para PT-BR (documentação pública)

---

## [1.0.0] - 2026-06-03

Tag: [`v1.0.0`](https://github.com/Magonitte/Chronos_Chat/releases/tag/v1.0.0)

### Adicionado

- Stack completa: LibreChat → LiteLLM (hub) → mem0, AnythingLLM, llama.cpp
- Orquestração em `config/litellm/orchestration/` + hooks `pre_call` / `post_call`
- Policies: `memory_policy`, `rag_policy`, context budget 131k
- Isolamento `X-User-Id` (`jean` / `tati`) fail-closed
- Chat texto + visão E2E, observabilidade, fallback llama offline
- Docker Compose, scripts de operação, 230+ testes pytest

[1.1.0]: https://github.com/Magonitte/Chronos_Chat/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Magonitte/Chronos_Chat/releases/tag/v1.0.0
