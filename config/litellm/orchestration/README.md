# orchestration/

Lógica de negócio do hub LiteLLM.

| Módulo | Interface planejada |
|--------|---------------------|
| `types.py` | `OrchestrationRequest`, `UserContext` |
| `context_budget.py` | `ContextBudget` — 20/30/20/30 |
| `user_id.py` | `extract_user_id(headers)` — allowlist, fail-closed |
| `context_builder.py` | `build(...)` → `BuiltContext` |
| `mem0_client.py` | `search(user_id, query)`, `add(user_id, messages)` |
| `rag_client.py` | `retrieve(workspace, query)` |
| `memory_policy.py` | `should_persist(conversation, response, ctx) → bool` |
| `rag_policy.py` | `should_trigger(query, user_context) → bool` |

Policies são testáveis isoladamente. Clients fazem HTTP — sem lógica de decisão.

**Regra:** nenhum módulo aqui importa LiteLLM — lógica pura.

Ver [README raiz](../../../README.md) (arquitetura e context budget) e `context_budget.py`.
