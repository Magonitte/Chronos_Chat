"""Montagem de contexto com budget 20/30/20/30 (ADR 002). Camada pura de orquestração."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence, TypeVar

from orchestration.context_budget import ContextBudget
from orchestration.types import ChatMessage, Memory, RagChunk

DEFAULT_CHARS_PER_TOKEN = 4
DEFAULT_IMAGE_TOKENS_PER_IMAGE = 1024
DEFAULT_SYSTEM_OVERHEAD_TOKENS = 512

MEM0_SECTION_HEADER = "## Memórias do usuário\n"
RAG_SECTION_HEADER = "## Documentos relevantes\n"

T = TypeVar("T")


@dataclass(frozen=True)
class ContextTokenBreakdown:
    """Contagem de tokens por fatia (estimativa chars/4)."""

    ctx_total: int
    reserve_response: int
    system_overhead: int
    image_tokens: int
    mem0_tokens: int
    rag_tokens: int
    conversation_tokens: int

    @property
    def total_input_tokens(self) -> int:
        return (
            self.system_overhead
            + self.image_tokens
            + self.mem0_tokens
            + self.rag_tokens
            + self.conversation_tokens
        )

    @property
    def total_with_reserve(self) -> int:
        return self.total_input_tokens + self.reserve_response

    def fits_ctx_total(self) -> bool:
        return self.total_with_reserve <= self.ctx_total


@dataclass(frozen=True)
class BuiltContext:
    """Resultado de build() — mensagens prontas para inferência."""

    messages: tuple[ChatMessage, ...]
    memories_used: tuple[Memory, ...]
    rag_chunks_used: tuple[RagChunk, ...]
    enriched_system: str
    breakdown: ContextTokenBreakdown


def estimate_tokens(text: str, *, chars_per_token: int = DEFAULT_CHARS_PER_TOKEN) -> int:
    """Estimativa de tokens (chars/4), mínimo 0."""
    if not text:
        return 0
    return max(0, (len(text) + chars_per_token - 1) // chars_per_token)


def _scaled_slice_cap(available: int, slice_pct: float, reserve_pct: float) -> int:
    """Cap proporcional quando available < 80% do ctx (ver context-budget.md)."""
    input_share = 1.0 - reserve_pct
    if input_share <= 0:
        return 0
    return int(available * slice_pct / input_share)


def _count_images(messages: Sequence[ChatMessage]) -> int:
    count = 0
    for msg in messages:
        if isinstance(msg.content, str):
            continue
        for part in msg.content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                count += 1
    return count


def message_content_tokens(
    msg: ChatMessage,
    *,
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
    image_tokens_per_image: int = DEFAULT_IMAGE_TOKENS_PER_IMAGE,
) -> int:
    """Tokens de uma mensagem (texto + imagens no payload multimodal)."""
    if isinstance(msg.content, str):
        return estimate_tokens(msg.content, chars_per_token=chars_per_token)
    total = 0
    for part in msg.content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            total += estimate_tokens(
                str(part.get("text", "")), chars_per_token=chars_per_token
            )
        elif part.get("type") == "image_url":
            total += image_tokens_per_image
    return total


def truncate_by_score(
    items: Sequence[T],
    budget_tokens: int,
    *,
    score_key: Callable[[T], float],
    format_item: Callable[[T], str],
    section_header: str = "",
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
) -> tuple[T, ...]:
    """Inclui itens por score decrescente até esgotar o budget."""
    if budget_tokens <= 0 or not items:
        return ()

    budget_left = budget_tokens
    if section_header:
        header_tokens = estimate_tokens(section_header, chars_per_token=chars_per_token)
        if header_tokens > budget_tokens:
            return ()
        budget_left -= header_tokens

    sorted_items = sorted(items, key=score_key, reverse=True)
    selected: list[T] = []
    for item in sorted_items:
        formatted = format_item(item)
        item_tokens = estimate_tokens(formatted, chars_per_token=chars_per_token)
        if item_tokens <= budget_left:
            selected.append(item)
            budget_left -= item_tokens
    return tuple(selected)


def format_memories(memories: Sequence[Memory]) -> str:
    if not memories:
        return ""
    lines = [MEM0_SECTION_HEADER.rstrip()]
    for memory in memories:
        lines.append(f"- {memory.text}")
    return "\n".join(lines) + "\n"


def format_rag_chunks(chunks: Sequence[RagChunk]) -> str:
    if not chunks:
        return ""
    parts: list[str] = [RAG_SECTION_HEADER.rstrip()]
    for chunk in chunks:
        parts.append(f"[Fonte: {chunk.source}]")
        parts.append(chunk.text)
    return "\n".join(parts) + "\n"


def truncate_messages_oldest_first(
    messages: Sequence[ChatMessage],
    budget_tokens: int,
    *,
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
    image_tokens_per_image: int = DEFAULT_IMAGE_TOKENS_PER_IMAGE,
) -> tuple[ChatMessage, ...]:
    """
    Remove mensagens antigas (não-system) se exceder budget.
    A última mensagem não-system é sempre preservada.
    """
    if budget_tokens <= 0 or not messages:
        return tuple(messages)

    system_msgs = [m for m in messages if m.role == "system"]
    non_system = [m for m in messages if m.role != "system"]

    if not non_system:
        return tuple(system_msgs)

    last = non_system[-1]
    middle = non_system[:-1]
    last_tokens = message_content_tokens(
        last,
        chars_per_token=chars_per_token,
        image_tokens_per_image=image_tokens_per_image,
    )

    budget_left = budget_tokens - last_tokens
    kept_middle: list[ChatMessage] = []
    for msg in reversed(middle):
        msg_tokens = message_content_tokens(
            msg,
            chars_per_token=chars_per_token,
            image_tokens_per_image=image_tokens_per_image,
        )
        if msg_tokens <= budget_left:
            kept_middle.insert(0, msg)
            budget_left -= msg_tokens

    return tuple(system_msgs) + tuple(kept_middle) + (last,)


def _merge_system_prompt(base: str, mem0_text: str, rag_text: str) -> str:
    parts = [p for p in (base.strip(), mem0_text.strip(), rag_text.strip()) if p]
    return "\n\n".join(parts)


def _replace_or_prepend_system(
    messages: Sequence[ChatMessage], enriched_system: str
) -> tuple[ChatMessage, ...]:
    if not enriched_system.strip():
        return tuple(messages)

    enriched = ChatMessage(role="system", content=enriched_system)
    rest = [m for m in messages if m.role != "system"]
    return (enriched,) + tuple(rest)


def _resolve_overhead_tokens(
    base_system_prompt: str,
    system_overhead_tokens: int | None,
    *,
    chars_per_token: int,
) -> int:
    if system_overhead_tokens is not None:
        return system_overhead_tokens
    if base_system_prompt.strip():
        return estimate_tokens(base_system_prompt, chars_per_token=chars_per_token)
    return DEFAULT_SYSTEM_OVERHEAD_TOKENS


def _image_tokens_from_env(
    environ: Mapping[str, str] | None,
    image_count: int,
    explicit_per_image: int | None,
) -> int:
    if image_count <= 0:
        return 0
    per_image = explicit_per_image
    if per_image is None and environ is not None:
        raw = environ.get("CTX_IMAGE_TOKENS_PER_IMAGE", "").strip()
        if raw:
            per_image = int(raw)
    if per_image is None:
        per_image = DEFAULT_IMAGE_TOKENS_PER_IMAGE
    return image_count * per_image


def build(
    *,
    messages: Sequence[ChatMessage],
    memories: Sequence[Memory],
    rag_chunks: Sequence[RagChunk],
    budget: ContextBudget | None = None,
    rag_active: bool = True,
    base_system_prompt: str = "",
    image_count: int | None = None,
    image_tokens_per_image: int | None = None,
    system_overhead_tokens: int | None = None,
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
    environ: Mapping[str, str] | None = None,
) -> BuiltContext:
    """
    Monta mensagens com mem0/RAG no system prompt e histórico truncado.

    Pipeline: overhead + imagens → mem0 (score) → RAG (score, se ativo) → conversa.
    """
    ctx_budget = budget if budget is not None else ContextBudget.default()
    env = environ if environ is not None else os.environ

    img_count = image_count if image_count is not None else _count_images(messages)
    image_tokens = _image_tokens_from_env(env, img_count, image_tokens_per_image)

    overhead = _resolve_overhead_tokens(
        base_system_prompt, system_overhead_tokens, chars_per_token=chars_per_token
    )

    available = (
        ctx_budget.ctx_total
        - ctx_budget.reserve_response_tokens
        - overhead
        - image_tokens
    )
    if available < 0:
        available = 0

    mem0_cap = min(
        ctx_budget.budget_mem0_tokens,
        _scaled_slice_cap(available, ctx_budget.budget_mem0_pct, ctx_budget.reserve_response_pct),
    )
    memories_used = truncate_by_score(
        memories,
        mem0_cap,
        score_key=lambda m: m.score,
        format_item=lambda m: f"- {m.text}\n",
        section_header=MEM0_SECTION_HEADER,
        chars_per_token=chars_per_token,
    )
    mem0_text = format_memories(memories_used)
    mem0_tokens = estimate_tokens(mem0_text, chars_per_token=chars_per_token)

    rag_tokens = 0
    rag_chunks_used: tuple[RagChunk, ...] = ()
    rag_text = ""
    if rag_active:
        rag_cap = min(
            ctx_budget.budget_rag_tokens,
            _scaled_slice_cap(
                available, ctx_budget.budget_rag_pct, ctx_budget.reserve_response_pct
            ),
        )
        rag_chunks_used = truncate_by_score(
            rag_chunks,
            rag_cap,
            score_key=lambda c: c.score,
            format_item=lambda c: f"[Fonte: {c.source}]\n{c.text}\n",
            section_header=RAG_SECTION_HEADER,
            chars_per_token=chars_per_token,
        )
        rag_text = format_rag_chunks(rag_chunks_used)
        rag_tokens = estimate_tokens(rag_text, chars_per_token=chars_per_token)

    remaining = available - mem0_tokens - rag_tokens
    if remaining < 0:
        remaining = 0

    chat_cap = min(ctx_budget.budget_conversation_tokens, remaining)
    enriched_system = _merge_system_prompt(base_system_prompt, mem0_text, rag_text)

    non_system_for_chat = [m for m in messages if m.role != "system"]
    truncated_non_system = truncate_messages_oldest_first(
        non_system_for_chat,
        chat_cap,
        chars_per_token=chars_per_token,
        image_tokens_per_image=image_tokens_per_image or DEFAULT_IMAGE_TOKENS_PER_IMAGE,
    )

    base_only = base_system_prompt.strip()
    system_overhead_count = (
        overhead
        if not base_only
        else estimate_tokens(base_only, chars_per_token=chars_per_token)
    )

    conversation_tokens = sum(
        message_content_tokens(
            m,
            chars_per_token=chars_per_token,
            image_tokens_per_image=image_tokens_per_image or DEFAULT_IMAGE_TOKENS_PER_IMAGE,
        )
        for m in truncated_non_system
    )

    out_messages = _replace_or_prepend_system(
        truncated_non_system, enriched_system if enriched_system.strip() else base_system_prompt
    )

    breakdown = ContextTokenBreakdown(
        ctx_total=ctx_budget.ctx_total,
        reserve_response=ctx_budget.reserve_response_tokens,
        system_overhead=system_overhead_count,
        image_tokens=image_tokens,
        mem0_tokens=mem0_tokens,
        rag_tokens=rag_tokens,
        conversation_tokens=conversation_tokens,
    )

    return BuiltContext(
        messages=out_messages,
        memories_used=memories_used,
        rag_chunks_used=rag_chunks_used,
        enriched_system=enriched_system,
        breakdown=breakdown,
    )
