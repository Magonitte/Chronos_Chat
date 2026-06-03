"""Testes de rag_client (HTTP mockado, sem AnythingLLM real)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from orchestration.rag_client import (
    RagClientConfig,
    _parse_vector_results,
    load_config,
    retrieve,
    workspace_slug_for_user,
)
from orchestration.types import RagChunk


def _cfg(**overrides: Any) -> RagClientConfig:
    base = RagClientConfig(
        api_url="http://anythingllm:3001",
        api_key="test-key",
        timeout=2.0,
        top_n=4,
        score_threshold=0.2,
        workspace_slugs={"jean": "jean-carlos-de-souza", "tati": "tatiane-schluter-de-souza"},
    )
    return replace(base, **overrides)


def test_workspace_slug_for_user() -> None:
    cfg = _cfg()
    assert workspace_slug_for_user("jean", config=cfg) == "jean-carlos-de-souza"
    assert workspace_slug_for_user("admin", config=cfg) is None


def test_load_config_workspace_slugs_from_env_json() -> None:
    cfg = load_config(
        {
            "ANYTHINGLLM_API_URL": "http://localhost:3001",
            "ANYTHINGLLM_API_KEY": "k",
            "RAG_WORKSPACE_SLUGS": '{"jean": "custom-jean"}',
        }
    )
    assert cfg.workspace_slugs["jean"] == "custom-jean"


def test_parse_vector_results_maps_source_and_score() -> None:
    data = {
        "results": [
            {
                "text": "conteúdo do chunk",
                "score": 0.88,
                "metadata": {"title": "livro-x.pdf", "chunkSource": "ignored-if-title"},
            },
            {"text": "", "score": 1.0},
            {
                "text": "outro",
                "distance": 0.2,
                "metadata": {},
            },
        ]
    }
    chunks = _parse_vector_results(data)
    assert len(chunks) == 2
    assert chunks[0].source == "livro-x.pdf"
    assert chunks[0].score == 0.88
    assert chunks[1].score == pytest.approx(0.8)


def test_retrieve_fail_open_on_http_error() -> None:
    def _fail(*_args: Any, **_kwargs: Any) -> None:
        return None

    assert retrieve("jean", "buscar nos meus documentos", config=_cfg(), post_json=_fail) == ()


def test_retrieve_fail_open_without_api_key() -> None:
    cfg = _cfg(api_key="")
    assert retrieve("jean", "no pdf", config=cfg) == ()


def test_retrieve_success() -> None:
    captured: dict[str, Any] = {}

    def _ok(url: str, payload: dict[str, Any], timeout: float, headers: dict[str, str]) -> dict[str, Any]:
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout"] = timeout
        captured["headers"] = headers
        return {
            "results": [
                {"text": "trecho", "score": 0.9, "metadata": {"title": "doc.pdf"}},
            ]
        }

    chunks = retrieve("tati", "no livro", config=_cfg(), post_json=_ok)
    assert len(chunks) == 1
    assert chunks[0] == RagChunk(text="trecho", source="doc.pdf", score=0.9, metadata={"title": "doc.pdf"})
    assert captured["url"].endswith("/api/v1/workspace/tatiane-schluter-de-souza/vector-search")
    assert captured["payload"]["query"] == "no livro"
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_retrieve_empty_query() -> None:
    assert retrieve("jean", "   ", config=_cfg()) == ()
