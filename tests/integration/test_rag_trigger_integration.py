"""
T8.1 — rag_policy: trigger vs não-trigger no chain pre_call real.

Cobre o contrato `docs/rag-flow.md`:
- RAG só dispara via `rag_policy.should_trigger(query, ctx)` — nunca `if keyword in prompt`.
- pre_call consulta rag_client.retrieve apenas quando policy retorna True.
- system prompt só ganha bloco `## Documentos relevantes` quando policy aprovou.
- ativo mesmo em saudações quando há workspace ativo na metadata.
- desativado por `newchat_rag_enabled=false` na metadata.
- combinado com mem0 sem cross-talk (memórias e chunks são fatias separadas).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hooks.pre_call import (
    METADATA_RAG_TRIGGERED_KEY,
    run_pre_call,
)
from orchestration.rag_policy import has_document_reference

from .conftest import (
    make_litellm_payload,
    patched_backends,
    rag_enabled_meta,
)


# ---------------------------------------------------------------------------
# Anti-padrão — código não pode usar `if keyword in prompt` em rag_policy
# ---------------------------------------------------------------------------


def test_rag_policy_source_has_no_naive_keyword_membership() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "litellm"
        / "orchestration"
        / "rag_policy.py"
    ).read_text(encoding="utf-8")
    naive = re.findall(r'if\s+["\'][^"\']+["\']\s+in\s+\w+', source)
    assert naive == [], f"padrão proibido encontrado em rag_policy: {naive}"


# ---------------------------------------------------------------------------
# Não-trigger
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "oi",
        "Olá, como vai?",
        "Qual a capital da França?",
        "Me explica receitas de bolo",
        "Preciso de uma receita simples",
        "python como listar arquivos",
        "O que é machine learning?",
        "Bom dia",
        "",
    ],
)
def test_no_rag_for_generic_or_topic_only_queries(query: str, patched_backends) -> None:
    _, rag = patched_backends
    data = make_litellm_payload("jean", query)
    run_pre_call(data)

    assert "jean" not in rag.retrieve_calls, f"RAG não deveria disparar para: {query!r}"
    assert data["metadata"][METADATA_RAG_TRIGGERED_KEY] is False
    for msg in data["messages"]:
        if msg.get("role") == "system":
            assert "## Documentos relevantes" not in str(msg.get("content", ""))


def test_rag_disabled_in_metadata_never_triggers(patched_backends) -> None:
    _, rag = patched_backends
    data = make_litellm_payload(
        "jean",
        "Buscar nos meus documentos sobre férias",
        meta=rag_enabled_meta(enabled=False),
    )
    run_pre_call(data)
    assert "jean" not in rag.retrieve_calls
    assert data["metadata"][METADATA_RAG_TRIGGERED_KEY] is False


# ---------------------------------------------------------------------------
# Trigger por frase de documento
# ---------------------------------------------------------------------------


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
def test_rag_triggers_for_document_reference(query: str, patched_backends) -> None:
    _, rag = patched_backends
    data = make_litellm_payload("jean", query)
    run_pre_call(data)

    assert "jean" in rag.retrieve_calls, f"RAG deveria disparar para: {query!r}"
    assert data["metadata"][METADATA_RAG_TRIGGERED_KEY] is True


# ---------------------------------------------------------------------------
# Trigger por workspace ativo
# ---------------------------------------------------------------------------


def test_rag_triggers_when_active_workspace(patched_backends) -> None:
    _, rag = patched_backends
    data = make_litellm_payload(
        "jean", "oi", meta=rag_enabled_meta(workspace="jean-personal")
    )
    run_pre_call(data)
    assert "jean" in rag.retrieve_calls


def test_rag_triggers_with_active_workspace_even_for_trivial_query(patched_backends) -> None:
    _, rag = patched_backends
    data = make_litellm_payload(
        "tati", "olá", meta=rag_enabled_meta(workspace="tati-cozinha")
    )
    run_pre_call(data)
    assert "tati" in rag.retrieve_calls
    assert "jean" not in rag.retrieve_calls


# ---------------------------------------------------------------------------
# RAG chunks no system prompt — apenas quando policy aprovou
# ---------------------------------------------------------------------------


def test_rag_chunks_injected_into_system_prompt_when_triggered(patched_backends) -> None:
    _, rag = patched_backends
    rag.stores["jean"] = [
        {"text": "trecho sobre férias", "score": 0.95, "metadata": {"title": "rh.pdf"}},
    ]
    data = make_litellm_payload("jean", "Buscar nos meus documentos sobre férias")
    run_pre_call(data)

    system = data["messages"][0]["content"]
    assert "## Documentos relevantes" in system
    assert "rh.pdf" in system
    assert "trecho sobre férias" in system


def test_rag_chunks_not_injected_when_not_triggered(patched_backends) -> None:
    _, rag = patched_backends
    rag.stores["jean"] = [
        {"text": "trecho irrelevante", "score": 0.95, "metadata": {"title": "x.pdf"}},
    ]
    data = make_litellm_payload("jean", "oi")
    run_pre_call(data)

    system = data["messages"][0]["content"]
    assert "## Documentos relevantes" not in system
    assert "trecho irrelevante" not in system


# ---------------------------------------------------------------------------
# Combinação mem0 + RAG — fatias separadas, sem cross-pollination
# ---------------------------------------------------------------------------


def test_mem0_and_rag_run_independently_in_pre_call(patched_backends) -> None:
    mem0, rag = patched_backends
    mem0.stores["jean"] = [
        {"id": "jean-1", "memory": "Jean gosta de café", "score": 0.9},
    ]
    rag.stores["jean"] = [
        {"text": "receita de bolo", "score": 0.9, "metadata": {"title": "receitas.pdf"}},
    ]

    data = make_litellm_payload("jean", "Buscar nos meus documentos sobre receitas")
    run_pre_call(data)

    system = data["messages"][0]["content"]
    assert "Memórias do usuário" in system
    assert "Jean gosta de café" in system
    assert "## Documentos relevantes" in system
    assert "receita de bolo" in system


def test_rag_trigger_flag_reflects_policy_in_metadata(patched_backends) -> None:
    _, rag = patched_backends
    cases = [
        ("O que diz o PDF?", True),
        ("O que diz o livro?", True),
        ("Use o RAG", True),
        ("Capital da França?", False),
        ("Oi", False),
    ]
    for query, expected in cases:
        data = make_litellm_payload("jean", query)
        run_pre_call(data)
        assert data["metadata"][METADATA_RAG_TRIGGERED_KEY] is expected, query


def test_rag_policy_uses_regex_not_naive_membership(patched_backends) -> None:
    """Sanity: rag_policy deve usar has_document_reference (regex)."""
    assert has_document_reference("Buscar nos meus documentos") is True
    assert has_document_reference("buscar nos meus documentos") is True
    assert has_document_reference("BUSCAR NOS MEUS DOCUMENTOS") is True
    assert has_document_reference("me conte uma receita") is False
    assert has_document_reference("documento") is False
