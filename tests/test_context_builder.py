"""Testes do context_builder (budget 20/30/20/30, truncagem por score)."""

from orchestration.context_budget import ContextBudget
from orchestration.context_builder import (
    DEFAULT_IMAGE_TOKENS_PER_IMAGE,
    build,
    estimate_tokens,
    format_memories,
    format_rag_chunks,
    message_content_tokens,
    truncate_by_score,
    truncate_messages_oldest_first,
)
from orchestration.types import ChatMessage, Memory, RagChunk


def _mem(id_suffix: int, text: str, score: float) -> Memory:
    return Memory(id=f"m{id_suffix}", text=text, score=score)


def _chunk(text: str, score: float, source: str = "doc.pdf") -> RagChunk:
    return RagChunk(text=text, source=source, score=score)


def test_estimate_tokens_chars_div_four() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 8) == 2


def test_truncate_by_score_prefers_higher_score() -> None:
    memories = [
        _mem(1, "low-" + ("x" * 80), 0.1),
        _mem(2, "high-" + ("y" * 80), 0.9),
        _mem(3, "mid-" + ("z" * 80), 0.5),
    ]
    selected = truncate_by_score(
        memories,
        30,
        score_key=lambda m: m.score,
        format_item=lambda m: f"- {m.text}\n",
        section_header="## Memórias do usuário\n",
    )
    assert len(selected) == 1
    assert selected[0].score == 0.9


def test_hundred_memories_within_mem0_budget() -> None:
    memories = [_mem(i, f"memory-{i}-" + ("x" * 1200), float(i) / 100) for i in range(100)]
    result = build(
        messages=[ChatMessage(role="user", content="oi")],
        memories=memories,
        rag_chunks=[],
        rag_active=False,
    )
    budget = ContextBudget.default()
    assert result.breakdown.mem0_tokens <= budget.budget_mem0_tokens
    assert len(result.memories_used) < len(memories)


def test_fifty_chunks_within_rag_budget() -> None:
    chunks = [
        _chunk(f"chunk-{i}-" + ("y" * 4000), float(i) / 50) for i in range(50)
    ]
    result = build(
        messages=[ChatMessage(role="user", content="pergunta")],
        memories=[],
        rag_chunks=chunks,
        rag_active=True,
    )
    budget = ContextBudget.default()
    assert result.breakdown.rag_tokens <= budget.budget_rag_tokens
    assert len(result.rag_chunks_used) < len(chunks)


def test_long_history_drops_oldest_keeps_last() -> None:
    msgs = [
        ChatMessage(role="user", content="antiga " + ("a" * 20_000)),
        ChatMessage(role="assistant", content="resposta " + ("b" * 20_000)),
        ChatMessage(role="user", content="atual"),
    ]
    small_budget = ContextBudget(
        ctx_total=4_000,
        reserve_response_pct=0.20,
        budget_conversation_pct=0.30,
        budget_mem0_pct=0.20,
        budget_rag_pct=0.30,
    )
    result = build(
        messages=msgs,
        memories=[],
        rag_chunks=[],
        budget=small_budget,
        rag_active=False,
        system_overhead_tokens=100,
        image_count=0,
    )
    roles_contents = [
        (m.role, m.content if isinstance(m.content, str) else m.content)
        for m in result.messages
        if m.role != "system"
    ]
    assert any(c == "atual" for _, c in roles_contents)
    assert not any(isinstance(c, str) and c.startswith("antiga") for _, c in roles_contents)


def test_image_reduces_text_budget() -> None:
    budget = ContextBudget.default()
    text_only = build(
        messages=[ChatMessage(role="user", content="hello")],
        memories=[],
        rag_chunks=[],
        image_count=0,
    )
    with_image = build(
        messages=[
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "hello"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                ],
            )
        ],
        memories=[],
        rag_chunks=[],
        image_count=1,
    )
    assert with_image.breakdown.image_tokens == DEFAULT_IMAGE_TOKENS_PER_IMAGE
    assert text_only.breakdown.image_tokens == 0
    assert (
        with_image.breakdown.mem0_tokens + with_image.breakdown.conversation_tokens
        <= text_only.breakdown.mem0_tokens + text_only.breakdown.conversation_tokens
        or with_image.breakdown.total_input_tokens
        >= text_only.breakdown.total_input_tokens
    )
    # available menor com imagem → menos memórias cabem com mesma fixture
    many = [_mem(i, "x" * 400, float(i)) for i in range(80)]
    text_mem = build(
        messages=[ChatMessage(role="user", content="q")],
        memories=many,
        rag_chunks=[],
        image_count=0,
    )
    img_mem = build(
        messages=[ChatMessage(role="user", content="q")],
        memories=many,
        rag_chunks=[],
        image_count=1,
    )
    assert len(img_mem.memories_used) <= len(text_mem.memories_used)


def test_rag_inactive_skips_chunks() -> None:
    chunks = [_chunk("important", 0.99)]
    result = build(
        messages=[ChatMessage(role="user", content="q")],
        memories=[],
        rag_chunks=chunks,
        rag_active=False,
    )
    assert result.rag_chunks_used == ()
    assert result.breakdown.rag_tokens == 0
    assert "Documentos relevantes" not in result.enriched_system


def test_build_fits_ctx_total() -> None:
    memories = [_mem(i, "mem " * 500, float(i)) for i in range(100)]
    chunks = [_chunk("chunk " * 400, float(i)) for i in range(50)]
    msgs = [
        ChatMessage(role="user", content="old " * 2000),
        ChatMessage(role="assistant", content="mid " * 2000),
        ChatMessage(role="user", content="now"),
    ]
    result = build(
        messages=msgs,
        memories=memories,
        rag_chunks=chunks,
        rag_active=True,
    )
    assert result.breakdown.fits_ctx_total()


def test_enriched_system_contains_mem0_and_rag() -> None:
    result = build(
        messages=[ChatMessage(role="user", content="q")],
        memories=[_mem(1, "gosta de café", 0.8)],
        rag_chunks=[_chunk("receita de bolo", 0.7, "livro.pdf")],
        rag_active=True,
        base_system_prompt="Você é um assistente.",
    )
    assert "Memórias do usuário" in result.enriched_system
    assert "gosta de café" in result.enriched_system
    assert "Documentos relevantes" in result.enriched_system
    assert "livro.pdf" in result.enriched_system
    assert result.messages[0].role == "system"


def test_truncate_messages_oldest_first_unit() -> None:
    msgs = [
        ChatMessage(role="user", content="1"),
        ChatMessage(role="user", content="2"),
        ChatMessage(role="user", content="keep"),
    ]
    kept = truncate_messages_oldest_first(msgs, budget_tokens=estimate_tokens("keep"))
    assert kept[-1].content == "keep"
    assert len(kept) == 1


def test_message_content_tokens_multimodal() -> None:
    msg = ChatMessage(
        role="user",
        content=[
            {"type": "text", "text": "abcd"},
            {"type": "image_url", "image_url": {"url": "http://x"}},
        ],
    )
    assert message_content_tokens(msg) == 1 + DEFAULT_IMAGE_TOKENS_PER_IMAGE


def test_format_helpers() -> None:
    assert format_memories([]) == ""
    assert "café" in format_memories([_mem(1, "café", 1.0)])
    assert format_rag_chunks([]) == ""
    assert "Fonte:" in format_rag_chunks([_chunk("texto", 1.0, "a.pdf")])
