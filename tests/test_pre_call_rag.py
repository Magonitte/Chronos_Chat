"""PRE-CALL: RAG condicional via rag_policy (rag_client mockado)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hooks.pre_call import METADATA_RAG_TRIGGERED_KEY, run_pre_call
from orchestration.types import RagChunk


def _data(content: str, *, meta: dict | None = None) -> dict:
    payload: dict = {
        "model": "newchat",
        "messages": [{"role": "user", "content": content}],
        "proxy_server_request": {"headers": {"X-User-Id": "jean"}},
    }
    if meta is not None:
        payload["metadata"] = meta
    return payload


def test_pre_call_skips_rag_without_policy_signal() -> None:
    data = _data("Qual a capital da França?")
    with patch("hooks.pre_call.rag_client.retrieve") as mock_retrieve:
        run_pre_call(data)
        mock_retrieve.assert_not_called()
    assert data["metadata"][METADATA_RAG_TRIGGERED_KEY] is False
    for msg in data["messages"]:
        if msg.get("role") == "system":
            assert "## Documentos relevantes" not in str(msg.get("content", ""))


def test_pre_call_invokes_rag_on_document_reference() -> None:
    chunk = RagChunk(text="trecho RAG", source="manual.pdf", score=0.95)
    with patch("hooks.pre_call.rag_client.retrieve", return_value=(chunk,)) as mock_retrieve:
        data = _data("Buscar nos meus documentos sobre férias")
        run_pre_call(data)
        mock_retrieve.assert_called_once_with("jean", "Buscar nos meus documentos sobre férias")
    assert data["metadata"][METADATA_RAG_TRIGGERED_KEY] is True
    system = data["messages"][0]
    assert system["role"] == "system"
    assert "manual.pdf" in system["content"]
    assert "## Documentos relevantes" in system["content"]


def test_pre_call_rag_disabled_in_metadata() -> None:
    with patch("hooks.pre_call.rag_client.retrieve") as mock_retrieve:
        data = _data(
            "buscar nos meus documentos",
            meta={"newchat_rag_enabled": "false"},
        )
        run_pre_call(data)
        mock_retrieve.assert_not_called()
    assert data["metadata"][METADATA_RAG_TRIGGERED_KEY] is False


def test_pre_call_rag_active_workspace_triggers() -> None:
    with patch("hooks.pre_call.rag_client.retrieve", return_value=()) as mock_retrieve:
        data = _data("oi", meta={"newchat_active_workspace": "jean-ws"})
        run_pre_call(data)
        mock_retrieve.assert_called_once()
