"""
Fixtures compartilhadas dos testes de integração (T8.1).

Simulam backends mem0 e AnythingLLM (isolados por user_id) com Python puro,
sem HTTP, sem rede. Validam o chain:

  pre_call  → validate user_id → mem0 search → rag_policy → rag retrieve
           → context_builder  → injetar system prompt

  post_call → memory_policy    → mem0 add (direct|async)

Os patches em `hooks.pre_call` e `hooks.post_call` reescrevem os posters HTTP
para falar com o fake backend (em memória).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

import pytest

from hooks.pre_call import (
    METADATA_ACTIVE_WORKSPACE_KEY,
    METADATA_CONVERSATION_KEY,
    METADATA_MEMORY_TEXTS_KEY,
    METADATA_RAG_ENABLED_KEY,
    METADATA_RAG_TRIGGERED_KEY,
    METADATA_USER_ID_KEY,
)
from orchestration.rag_client import RagClientConfig


@dataclass
class FakeMem0Backend:
    """Backend mem0 em memória: stores por user_id; garante isolamento jean|tati."""

    stores: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    add_calls: list[dict[str, Any]] = field(default_factory=list)
    search_calls: list[dict[str, Any]] = field(default_factory=list)
    fail_next: bool = False

    def _store(self, user_id: str) -> list[dict[str, Any]]:
        return self.stores.setdefault(user_id, [])

    def add(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if self.fail_next:
            return None
        self.add_calls.append({"user_id": user_id, "payload": payload})
        text = (payload.get("messages") or [{}])[0].get("content", "")
        if payload.get("infer") is False and text:
            self._store(user_id).append(
                {"id": f"{user_id}-{len(self._store(user_id)) + 1}", "memory": text, "score": 0.9}
            )
        return {"results": []}

    def search(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if self.fail_next:
            return None
        self.search_calls.append({"user_id": user_id, "payload": payload})
        return {"results": list(self._store(user_id))}


@dataclass
class FakeRagBackend:
    """Backend AnythingLLM em memória: vector-search por user_id (workspace)."""

    stores: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    retrieve_calls: list[dict[str, Any]] = field(default_factory=dict)
    fail_next: bool = False

    def _store(self, user_id: str) -> list[dict[str, Any]]:
        return self.stores.setdefault(user_id, [])

    def retrieve(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if self.fail_next:
            return None
        self.retrieve_calls.setdefault(user_id, []).append(payload)
        return {"results": list(self._store(user_id))}


@pytest.fixture
def mem0_backend() -> FakeMem0Backend:
    return FakeMem0Backend()


@pytest.fixture
def rag_backend() -> FakeRagBackend:
    return FakeRagBackend()


@pytest.fixture
def rag_config() -> RagClientConfig:
    return RagClientConfig(
        api_url="http://anythingllm-test:3001",
        api_key="test-key",
        timeout=2.0,
        top_n=4,
        score_threshold=0.0,
        workspace_slugs={"jean": "jean-ws", "tati": "tati-ws"},
    )


@pytest.fixture
def patched_backends(
    mem0_backend: FakeMem0Backend,
    rag_backend: FakeRagBackend,
    rag_config: RagClientConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[FakeMem0Backend, FakeRagBackend]]:

    def _mem0_post(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any] | None:
        user_id = payload.get("user_id", "")
        if url.endswith("/search"):
            return mem0_backend.search(user_id, payload)
        if url.endswith("/memories"):
            return mem0_backend.add(user_id, payload)
        return None

    def _rag_post(
        url: str,
        payload: dict[str, Any],
        timeout: float,
        headers: dict[str, str],
    ) -> dict[str, Any] | None:
        for user_id, slug in rag_config.workspace_slugs.items():
            if f"/workspace/{slug}/" in url:
                return rag_backend.retrieve(user_id, payload)
        return None

    monkeypatch.setattr("hooks.pre_call.mem0_client._post_json", _mem0_post)
    monkeypatch.setattr("hooks.post_call.mem0_client._post_json", _mem0_post)
    monkeypatch.setattr("hooks.pre_call.rag_client._post_json", _rag_post)
    monkeypatch.setattr("orchestration.mem0_client._post_json", _mem0_post)
    monkeypatch.setattr("orchestration.rag_client._post_json", _rag_post)
    monkeypatch.setattr("orchestration.rag_client.load_config", lambda: rag_config)
    monkeypatch.setattr("orchestration.mem0_client.load_config", lambda: _default_mem0_config())
    monkeypatch.setattr("hooks.pre_call.rag_client.load_config", lambda: rag_config)
    monkeypatch.setattr("hooks.pre_call.mem0_client.load_config", lambda: _default_mem0_config())
    monkeypatch.setattr("hooks.post_call.mem0_client.load_config", lambda: _default_mem0_config())

    yield mem0_backend, rag_backend


def _default_mem0_config():
    from orchestration.mem0_client import Mem0ClientConfig

    return Mem0ClientConfig(
        api_url="http://mem0-test:8000",
        timeout=2.0,
        add_timeout=120.0,
        search_limit=10,
        min_score=0.0,
    )


def make_litellm_payload(
    user_id: str | None,
    content: str,
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta payload no formato que custom_callbacks/hooks recebem."""
    headers: dict[str, str] = {}
    if user_id is not None:
        headers["X-User-Id"] = user_id

    payload: dict[str, Any] = {
        "model": "newchat",
        "messages": [{"role": "user", "content": content}],
        "proxy_server_request": {"headers": headers},
    }
    if meta is not None:
        payload["metadata"] = dict(meta)
    return payload


def make_post_call_payload(
    user_id: str,
    conversation: list[dict[str, str]],
    *,
    memory_texts: list[str] | None = None,
    rag_triggered: bool = False,
) -> dict[str, Any]:
    """Monta payload no formato do post_call (data vem de metadata do pre_call)."""
    return {
        "metadata": {
            METADATA_USER_ID_KEY: user_id,
            METADATA_CONVERSATION_KEY: conversation,
            METADATA_MEMORY_TEXTS_KEY: list(memory_texts or []),
            METADATA_RAG_TRIGGERED_KEY: rag_triggered,
        }
    }


def make_post_call_response(content: str) -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def rag_enabled_meta(enabled: bool = True, workspace: str | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {METADATA_RAG_ENABLED_KEY: enabled}
    if workspace is not None:
        meta[METADATA_ACTIVE_WORKSPACE_KEY] = workspace
    return meta


__all__ = [
    "FakeMem0Backend",
    "FakeRagBackend",
    "make_litellm_payload",
    "make_post_call_payload",
    "make_post_call_response",
    "patched_backends",
    "rag_enabled_meta",
    "rag_config",
    "METADATA_USER_ID_KEY",
    "METADATA_CONVERSATION_KEY",
    "METADATA_MEMORY_TEXTS_KEY",
    "METADATA_RAG_TRIGGERED_KEY",
    "METADATA_RAG_ENABLED_KEY",
    "METADATA_ACTIVE_WORKSPACE_KEY",
]
