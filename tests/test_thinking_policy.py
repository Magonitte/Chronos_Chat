"""Testes unitarios para thinking_policy (F10 / T10.1)."""

from __future__ import annotations

from orchestration.thinking_policy import ThinkingContext, should_enable
from orchestration.types import ChatMessage


def _msg(role: str, content: str) -> ChatMessage:
    return ChatMessage(role=role, content=content)


def test_system_request_false() -> None:
    ctx = ThinkingContext(
        query="explique a relatividade",
        conversation=(),
        rag_chunk_count=0,
        has_images=False,
        is_system_request=True,
    )
    assert should_enable(ctx) is False


def test_trivial_query_false() -> None:
    ctx = ThinkingContext(
        query="oi",
        conversation=(),
        rag_chunk_count=0,
        has_images=False,
        is_system_request=False,
    )
    assert should_enable(ctx) is False


def test_trivial_query_obrigado_false() -> None:
    ctx = ThinkingContext(
        query="obrigado!",
        conversation=(),
        rag_chunk_count=0,
        has_images=False,
        is_system_request=False,
    )
    assert should_enable(ctx) is False


def test_recall_query_false() -> None:
    ctx = ThinkingContext(
        query="voce lembra o que eu disse?",
        conversation=(),
        rag_chunk_count=0,
        has_images=False,
        is_system_request=False,
    )
    assert should_enable(ctx) is False


def test_memory_command_false() -> None:
    ctx = ThinkingContext(
        query="lembre que eu gosto de pizza",
        conversation=(),
        rag_chunk_count=0,
        has_images=False,
        is_system_request=False,
    )
    assert should_enable(ctx) is False


def test_disabled_env_false() -> None:
    ctx = ThinkingContext(
        query="analise a complexidade deste algoritmo",
        conversation=(),
        rag_chunk_count=0,
        has_images=False,
        is_system_request=False,
    )
    env = {"NEWCHAT_THINKING_ENABLED": "false"}
    assert should_enable(ctx, environ=env) is False


def test_rag_many_chunks_true() -> None:
    ctx = ThinkingContext(
        query="explique a teoria da relatividade",
        conversation=(),
        rag_chunk_count=4,
        has_images=False,
        is_system_request=False,
    )
    assert should_enable(ctx) is True


def test_rag_few_chunks_false() -> None:
    ctx = ThinkingContext(
        query="oi",
        conversation=(),
        rag_chunk_count=1,
        has_images=False,
        is_system_request=False,
    )
    assert should_enable(ctx) is False


def test_long_conversation_true() -> None:
    conv = (
        _msg("user", "ola"),
        _msg("assistant", "oi, tudo bem?"),
        _msg("user", "me fale sobre python"),
        _msg("assistant", "python e uma linguagem de programacao..."),
        _msg("user", "quais as vantagens?"),
        _msg("assistant", "simplicidade, legibilidade..."),
        _msg("user", "e desvantagens?"),
        _msg("assistant", "desempenho inferior a C..."),
        _msg("user", "me fale sobre machine learning"),
    )
    ctx = ThinkingContext(
        query="me fale sobre machine learning",
        conversation=conv,
        rag_chunk_count=0,
        has_images=False,
        is_system_request=False,
    )
    assert should_enable(ctx) is True


def test_complex_query_true() -> None:
    ctx = ThinkingContext(
        query="analise as diferencas entre python e rust para sistemas embarcados",
        conversation=(),
        rag_chunk_count=0,
        has_images=False,
        is_system_request=False,
    )
    assert should_enable(ctx) is True
