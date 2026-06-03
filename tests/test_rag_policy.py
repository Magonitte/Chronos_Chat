"""Testes de rag_policy.should_trigger (sem HTTP, sem litellm)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from orchestration.rag_policy import has_document_reference, should_trigger
from orchestration.types import UserContext


def _ctx(
    *,
    user_id: str = "jean",
    rag_enabled: bool = True,
    active_workspace: str | None = None,
) -> UserContext:
    return UserContext(
        user_id=user_id,
        rag_enabled=rag_enabled,
        active_workspace=active_workspace,
    )


@pytest.mark.parametrize(
    ("query", "workspace"),
    [
        ("Olá, como vai?", None),
        ("Qual a capital da França?", None),
        ("Me explica receitas de bolo", None),
        ("Preciso de uma receita simples", None),
        ("", None),
    ],
)
def test_should_trigger_false_without_signals(query: str, workspace: str | None) -> None:
    assert should_trigger(query, _ctx(active_workspace=workspace)) is False


@pytest.mark.parametrize(
    "query",
    [
        "receita",
        "python",
        "bolo",
        "documento",
    ],
)
def test_topic_or_single_token_keywords_do_not_trigger(query: str) -> None:
    """Anti-padrão: keyword solta de tópico não aciona RAG."""
    assert should_trigger(query, _ctx()) is False
    assert has_document_reference(query) is False


@pytest.mark.parametrize(
    "query",
    [
        "O que diz o livro sobre isso?",
        "Segundo o PDF, qual é o procedimento?",
        "Buscar nos meus documentos sobre férias",
        "Consultar o documento que enviei ontem",
        "No meu arquivo contrato.pdf tem alguma cláusula?",
        "Use o RAG para esta pergunta",
        "Pesquisar nos documentos da pasta",
    ],
)
def test_should_trigger_true_on_document_reference(query: str) -> None:
    assert should_trigger(query, _ctx()) is True


def test_should_trigger_true_when_active_workspace() -> None:
    ctx = _ctx(active_workspace="esposa-workspace")
    assert should_trigger("oi", ctx) is True
    assert should_trigger("", ctx) is True


def test_should_trigger_false_when_rag_disabled() -> None:
    ctx = _ctx(rag_enabled=False, active_workspace="ws")
    assert should_trigger("buscar nos meus documentos", ctx) is False


def test_has_document_reference_empty_and_whitespace() -> None:
    assert has_document_reference("") is False
    assert has_document_reference("   ") is False


def test_rag_policy_does_not_use_naive_keyword_membership() -> None:
    """Garante ausência de `if "palavra" in prompt` no módulo."""
    source = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "litellm"
        / "orchestration"
        / "rag_policy.py"
    ).read_text(encoding="utf-8")
    assert ' in query' not in source or "pattern.search" in source
    naive = re.findall(r'if\s+["\'][^"\']+["\']\s+in\s+\w+', source)
    assert naive == [], f"padrão proibido encontrado: {naive}"
