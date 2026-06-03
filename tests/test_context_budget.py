"""Testes do context budget (131k, 20/30/20/30)."""

from orchestration.context_budget import (
    DEFAULT_BUDGET_CONVERSATION_TOKENS,
    DEFAULT_BUDGET_MEM0_TOKENS,
    DEFAULT_BUDGET_RAG_TOKENS,
    DEFAULT_RESERVE_RESPONSE_TOKENS,
    ContextBudget,
)


def test_default_token_slices() -> None:
    budget = ContextBudget.default()
    assert budget.ctx_total == 131_072
    assert budget.reserve_response_tokens == DEFAULT_RESERVE_RESPONSE_TOKENS == 26_214
    assert budget.budget_conversation_tokens == DEFAULT_BUDGET_CONVERSATION_TOKENS == 39_322
    assert budget.budget_mem0_tokens == DEFAULT_BUDGET_MEM0_TOKENS == 26_214
    assert budget.budget_rag_tokens == DEFAULT_BUDGET_RAG_TOKENS == 39_322


def test_default_percentages() -> None:
    budget = ContextBudget.default()
    assert budget.reserve_response_pct == 0.20
    assert budget.budget_conversation_pct == 0.30
    assert budget.budget_mem0_pct == 0.20
    assert budget.budget_rag_pct == 0.30


def test_max_combined_input_is_eighty_percent() -> None:
    budget = ContextBudget.default()
    # 80% de 131072; fatias arredondadas somam 104858 (docs ~104857)
    assert budget.max_combined_input_tokens == 104_858
    assert (
        budget.budget_conversation_tokens
        + budget.budget_mem0_tokens
        + budget.budget_rag_tokens
        == budget.max_combined_input_tokens
    )
    assert budget.input_and_reserve_tokens == 131_072


def test_from_env_uses_ctx_variables() -> None:
    budget = ContextBudget.from_env(
        {
            "CTX_TOTAL": "100000",
            "CTX_RESERVE_RESPONSE_PCT": "0.25",
            "CTX_BUDGET_CONVERSATION_PCT": "0.25",
            "CTX_BUDGET_MEM0_PCT": "0.25",
            "CTX_BUDGET_RAG_PCT": "0.25",
        }
    )
    assert budget.ctx_total == 100_000
    assert budget.reserve_response_tokens == 25_000
    assert budget.budget_conversation_tokens == 25_000
    assert budget.budget_mem0_tokens == 25_000
    assert budget.budget_rag_tokens == 25_000


def test_from_env_empty_uses_defaults() -> None:
    budget = ContextBudget.from_env({})
    assert budget.reserve_response_tokens == 26_214
    assert budget.budget_rag_tokens == 39_322
