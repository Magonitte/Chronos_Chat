"""Alocação explícita do contexto de 131k tokens (ADR 002)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from orchestration.types import (
    DEFAULT_BUDGET_CONVERSATION_PCT,
    DEFAULT_BUDGET_MEM0_PCT,
    DEFAULT_BUDGET_RAG_PCT,
    DEFAULT_CTX_TOTAL,
    DEFAULT_RESERVE_RESPONSE_PCT,
)

# Tokens documentados para ctx_total=131072 e percentuais padrão
DEFAULT_RESERVE_RESPONSE_TOKENS = 26_214
DEFAULT_BUDGET_CONVERSATION_TOKENS = 39_322
DEFAULT_BUDGET_MEM0_TOKENS = 26_214
DEFAULT_BUDGET_RAG_TOKENS = 39_322


def _parse_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


def _parse_float(value: str | None, default: float) -> float:
    if value is None or value.strip() == "":
        return default
    return float(value)


def _pct_to_tokens(ctx_total: int, pct: float) -> int:
    """Converte percentual em tokens (arredondamento compatível com docs)."""
    return round(ctx_total * pct)


@dataclass(frozen=True)
class ContextBudget:
    """
    Fatias do contexto llama-server (ctx_total).

    Resposta reservada: 20% | Conversa: 30% | mem0: 20% | RAG: 30%.
    """

    ctx_total: int = DEFAULT_CTX_TOTAL
    reserve_response_pct: float = DEFAULT_RESERVE_RESPONSE_PCT
    budget_conversation_pct: float = DEFAULT_BUDGET_CONVERSATION_PCT
    budget_mem0_pct: float = DEFAULT_BUDGET_MEM0_PCT
    budget_rag_pct: float = DEFAULT_BUDGET_RAG_PCT

    @property
    def reserve_response_tokens(self) -> int:
        return _pct_to_tokens(self.ctx_total, self.reserve_response_pct)

    @property
    def budget_conversation_tokens(self) -> int:
        return _pct_to_tokens(self.ctx_total, self.budget_conversation_pct)

    @property
    def budget_mem0_tokens(self) -> int:
        return _pct_to_tokens(self.ctx_total, self.budget_mem0_pct)

    @property
    def budget_rag_tokens(self) -> int:
        return _pct_to_tokens(self.ctx_total, self.budget_rag_pct)

    @property
    def max_combined_input_tokens(self) -> int:
        """Fatias de entrada (conversa + mem0 + RAG) — 80% do ctx_total (~104857)."""
        return self.ctx_total - self.reserve_response_tokens

    @property
    def input_and_reserve_tokens(self) -> int:
        """Verificação: entrada + reserva deve caber em ctx_total."""
        return self.max_combined_input_tokens + self.reserve_response_tokens

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ContextBudget:
        """Carrega overrides opcionais CTX_* do ambiente."""
        env = environ if environ is not None else os.environ
        return cls(
            ctx_total=_parse_int(env.get("CTX_TOTAL"), DEFAULT_CTX_TOTAL),
            reserve_response_pct=_parse_float(
                env.get("CTX_RESERVE_RESPONSE_PCT"), DEFAULT_RESERVE_RESPONSE_PCT
            ),
            budget_conversation_pct=_parse_float(
                env.get("CTX_BUDGET_CONVERSATION_PCT"), DEFAULT_BUDGET_CONVERSATION_PCT
            ),
            budget_mem0_pct=_parse_float(
                env.get("CTX_BUDGET_MEM0_PCT"), DEFAULT_BUDGET_MEM0_PCT
            ),
            budget_rag_pct=_parse_float(
                env.get("CTX_BUDGET_RAG_PCT"), DEFAULT_BUDGET_RAG_PCT
            ),
        )

    @classmethod
    def default(cls) -> ContextBudget:
        """Budget padrão (131072, 20/30/20/30)."""
        return cls()
