"""Tipos de domínio da orquestração (sem dependência LiteLLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

UserId = Literal["jean", "tati"]

# Percentuais padrão sobre ctx_total (ADR 002 / context-budget.md)
DEFAULT_RESERVE_RESPONSE_PCT = 0.20
DEFAULT_BUDGET_CONVERSATION_PCT = 0.30
DEFAULT_BUDGET_MEM0_PCT = 0.20
DEFAULT_BUDGET_RAG_PCT = 0.30

DEFAULT_CTX_TOTAL = 131_072


@dataclass(frozen=True)
class ChatMessage:
    """Mensagem de chat normalizada (hooks convertem do payload LiteLLM)."""

    role: str
    content: str | list[dict[str, Any]]


@dataclass(frozen=True)
class Memory:
    """Memória episódica retornada pelo mem0."""

    id: str
    text: str
    score: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RagChunk:
    """Chunk de documento retornado pelo AnythingLLM."""

    text: str
    source: str
    score: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UserContext:
    """Contexto de sessão para policies (ex.: rag_policy.should_trigger)."""

    user_id: str
    rag_enabled: bool = True
    active_workspace: str | None = None


@dataclass(frozen=True)
class OrchestrationRequest:
    """Request de domínio após validação de user_id no hook."""

    user_id: str
    messages: tuple[ChatMessage, ...]
    model: str | None = None
    has_images: bool = False

    @classmethod
    def from_messages(
        cls,
        *,
        user_id: str,
        messages: Sequence[ChatMessage],
        model: str | None = None,
        has_images: bool = False,
    ) -> OrchestrationRequest:
        return cls(
            user_id=user_id,
            messages=tuple(messages),
            model=model,
            has_images=has_images,
        )
