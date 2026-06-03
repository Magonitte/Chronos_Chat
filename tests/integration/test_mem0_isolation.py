"""
T8.1 — Isolamento de memórias mem0 entre jean e tati.

Garante que:
- pre_call chama mem0 search sempre com `user_id` do header validado;
- memórias injetadas no system prompt vêm apenas do user correto;
- post_call grava mem0 add com `user_id` correto (memórias de jean não vazam
  para tati e vice-versa);
- RAG também é filtrado por user_id (workspace slug diferente por usuário).
"""

from __future__ import annotations

import pytest

from hooks.pre_call import (
    METADATA_MEMORY_TEXTS_KEY,
    METADATA_RAG_TRIGGERED_KEY,
    METADATA_USER_ID_KEY,
    run_pre_call,
)
from hooks.post_call import run_post_call

from .conftest import (
    make_litellm_payload,
    make_post_call_payload,
    make_post_call_response,
    patched_backends,
    rag_enabled_meta,
)


# ---------------------------------------------------------------------------
# PRE-CALL — search sempre carrega user_id validado
# ---------------------------------------------------------------------------


def test_pre_call_search_carries_validated_user_id(patched_backends) -> None:
    mem0, _ = patched_backends
    data = make_litellm_payload("jean", "Qual a capital da França?")
    run_pre_call(data)

    assert mem0.search_calls, "mem0 search deveria ter sido chamado"
    assert mem0.search_calls[0]["payload"]["user_id"] == "jean"


def test_pre_call_search_uses_tati_user_id_for_tati(patched_backends) -> None:
    mem0, _ = patched_backends
    data = make_litellm_payload("tati", "minhas preferências?")
    run_pre_call(data)
    assert mem0.search_calls[0]["payload"]["user_id"] == "tati"


def test_pre_call_skips_mem0_search_on_trivial_message(patched_backends) -> None:
    mem0, _ = patched_backends
    data = make_litellm_payload("jean", "oi")
    run_pre_call(data)
    assert mem0.search_calls == []


# ---------------------------------------------------------------------------
# Isolamento jean vs tati — search vê apenas memórias do próprio user
# ---------------------------------------------------------------------------


def test_search_returns_only_jean_memories_for_jean(patched_backends) -> None:
    mem0, _ = patched_backends
    mem0.stores["jean"] = [
        {"id": "jean-1", "memory": "Jean gosta de café", "score": 0.9},
    ]
    mem0.stores["tati"] = [
        {"id": "tati-1", "memory": "Tati gosta de chá", "score": 0.95},
    ]

    data = make_litellm_payload("jean", "minhas preferências?")
    run_pre_call(data)

    jeans_memories = data["metadata"][METADATA_MEMORY_TEXTS_KEY]
    assert jeans_memories == ["Jean gosta de café"]
    assert "Tati gosta de chá" not in jeans_memories


def test_search_returns_only_tati_memories_for_tati(patched_backends) -> None:
    mem0, _ = patched_backends
    mem0.stores["jean"] = [
        {"id": "jean-1", "memory": "Jean gosta de café", "score": 0.9},
    ]
    mem0.stores["tati"] = [
        {"id": "tati-1", "memory": "Tati gosta de chá", "score": 0.95},
    ]

    data = make_litellm_payload("tati", "minhas preferências?")
    run_pre_call(data)

    tatis_memories = data["metadata"][METADATA_MEMORY_TEXTS_KEY]
    assert tatis_memories == ["Tati gosta de chá"]
    assert "Jean gosta de café" not in tatis_memories


def test_pre_call_system_prompt_injected_memories_match_user(patched_backends) -> None:
    mem0, _ = patched_backends
    mem0.stores["jean"] = [
        {"id": "jean-1", "memory": "Jean mora em SP", "score": 0.9},
    ]
    mem0.stores["tati"] = [
        {"id": "tati-1", "memory": "Tati mora em Curitiba", "score": 0.9},
    ]

    data_jean = make_litellm_payload("jean", "Onde eu moro?")
    run_pre_call(data_jean)
    system_jean = data_jean["messages"][0]["content"]
    assert "Jean mora em SP" in system_jean
    assert "Tati mora em Curitiba" not in system_jean

    data_tati = make_litellm_payload("tati", "Onde eu moro?")
    run_pre_call(data_tati)
    system_tati = data_tati["messages"][0]["content"]
    assert "Tati mora em Curitiba" in system_tati
    assert "Jean mora em SP" not in system_tati


# ---------------------------------------------------------------------------
# POST-CALL — add usa user_id do metadata (validado no pre_call)
# ---------------------------------------------------------------------------


def test_post_call_persists_jean_personal_fact_into_jean_store(patched_backends) -> None:
    mem0, _ = patched_backends
    data = make_post_call_payload(
        user_id="jean",
        conversation=[{"role": "user", "content": "Meu nome é Jean"}],
    )
    run_post_call(data, make_post_call_response("Prazer, Jean!"))

    assert mem0.add_calls, "mem0 add deveria ter sido chamado"
    assert mem0.add_calls[0]["user_id"] == "jean"
    assert mem0.stores["jean"], "loja de jean deveria ter a memória"
    assert mem0.stores["jean"][0]["memory"] == "Meu nome é Jean"
    assert "tati" not in mem0.stores


def test_post_call_persists_tati_personal_fact_into_tati_store(patched_backends) -> None:
    mem0, _ = patched_backends
    data = make_post_call_payload(
        user_id="tati",
        conversation=[{"role": "user", "content": "Meu nome é Tatiane"}],
    )
    run_post_call(data, make_post_call_response("Prazer!"))

    assert mem0.add_calls[0]["user_id"] == "tati"
    assert mem0.stores["tati"][0]["memory"] == "Meu nome é Tatiane"
    assert "jean" not in mem0.stores


def test_post_call_sequential_jean_then_tati_no_cross_write(patched_backends) -> None:
    """Dois post_calls seguidos: cada add grava só na loja do user_id do metadata."""
    mem0, _ = patched_backends

    run_post_call(
        make_post_call_payload(
            user_id="jean",
            conversation=[{"role": "user", "content": "Meu nome é Jean"}],
        ),
        make_post_call_response("Prazer, Jean!"),
    )
    run_post_call(
        make_post_call_payload(
            user_id="tati",
            conversation=[{"role": "user", "content": "Meu nome é Tatiane"}],
        ),
        make_post_call_response("Prazer!"),
    )

    assert len(mem0.add_calls) == 2
    assert [c["user_id"] for c in mem0.add_calls] == ["jean", "tati"]
    assert mem0.stores["jean"]
    assert not any("Tatiane" in m["memory"] for m in mem0.stores["jean"])
    assert mem0.stores["tati"]
    assert not any("Jean" in m["memory"] for m in mem0.stores["tati"])


# ---------------------------------------------------------------------------
# Fluxo completo PRE+POST — round-trip jean e tati
# ---------------------------------------------------------------------------


def test_full_round_trip_jean_seeds_and_recovers(patched_backends) -> None:
    mem0, _ = patched_backends
    mem0.stores["jean"] = [
        {"id": "jean-existing", "memory": "Jean gosta de café", "score": 0.9},
    ]

    pre = make_litellm_payload("jean", "Lembre que meu café preferido é espresso")
    run_pre_call(pre)
    assert pre["metadata"][METADATA_USER_ID_KEY] == "jean"
    assert any("Jean gosta de café" in t for t in pre["metadata"][METADATA_MEMORY_TEXTS_KEY])

    post = make_post_call_payload(
        user_id="jean",
        conversation=[{"role": "user", "content": "Lembre que meu café preferido é espresso"}],
        memory_texts=pre["metadata"][METADATA_MEMORY_TEXTS_KEY],
    )
    run_post_call(post, make_post_call_response("Anotado!"))

    assert mem0.add_calls[0]["user_id"] == "jean"
    assert mem0.stores["jean"][-1]["memory"] == "meu café preferido é espresso"


def test_full_round_trip_tati_does_not_see_jean_data(patched_backends) -> None:
    mem0, _ = patched_backends
    mem0.stores["jean"] = [
        {"id": "jean-1", "memory": "Jean gosta de café", "score": 0.9},
    ]

    pre = make_litellm_payload("tati", "oi")
    run_pre_call(pre)

    assert pre["metadata"][METADATA_USER_ID_KEY] == "tati"
    assert pre["metadata"][METADATA_MEMORY_TEXTS_KEY] == []
    for msg in pre["messages"]:
        if msg.get("role") == "system":
            assert "Jean" not in msg.get("content", "")


# ---------------------------------------------------------------------------
# RAG — workspace slug diferente por user_id (também isolamento)
# ---------------------------------------------------------------------------


def test_rag_workspace_is_user_specific(patched_backends) -> None:
    mem0, rag = patched_backends
    rag.stores["jean"] = [
        {"text": "doc do jean", "score": 0.9, "metadata": {"title": "jean.pdf"}},
    ]
    rag.stores["tati"] = [
        {"text": "doc da tati", "score": 0.9, "metadata": {"title": "tati.pdf"}},
    ]

    data = make_litellm_payload(
        "jean", "Buscar nos meus documentos", meta=rag_enabled_meta()
    )
    run_pre_call(data)

    assert "jean" in rag.retrieve_calls
    assert "tati" not in rag.retrieve_calls

    system = data["messages"][0]["content"]
    assert "jean.pdf" in system
    assert "tati.pdf" not in system


# ---------------------------------------------------------------------------
# Fail-open (mem0 offline) — não vaza memórias entre users
# ---------------------------------------------------------------------------


def test_pre_call_fail_open_mem0_returns_no_memories_for_either_user(
    patched_backends,
) -> None:
    mem0, _ = patched_backends
    mem0.fail_next = True

    for uid in ("jean", "tati"):
        data = make_litellm_payload(uid, "minhas preferências?")
        run_pre_call(data)
        assert data["metadata"][METADATA_MEMORY_TEXTS_KEY] == []
        assert data["metadata"][METADATA_USER_ID_KEY] == uid
