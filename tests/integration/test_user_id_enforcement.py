"""
T8.1 — X-User-Id: obrigatório, rejeitado quando inválido, propagado no chain.

Cobre o contrato `docs/user-id-contract.md` (fail-closed, sem fallback, allowlist
jean|tati) ao nível do chain pre_call → metadata → post_call.
"""

from __future__ import annotations

import pytest

from fastapi import HTTPException

from hooks.pre_call import METADATA_USER_ID_KEY, run_pre_call
from hooks.post_call import run_post_call
from orchestration.user_id import (
    ALLOWED_USER_IDS,
    InvalidUserIdError,
    extract_user_id,
)

from .conftest import (
    make_litellm_payload,
    make_post_call_payload,
    make_post_call_response,
    patched_backends,
)


@pytest.mark.parametrize("user_id", sorted(ALLOWED_USER_IDS))
def test_extract_user_id_accepts_allowlist_members(user_id: str) -> None:
    assert extract_user_id({"X-User-Id": user_id}) == user_id


@pytest.mark.parametrize("user_id", sorted(ALLOWED_USER_IDS))
def test_pre_call_writes_validated_user_id_to_metadata(
    user_id: str, patched_backends
) -> None:
    _, _ = patched_backends
    data = make_litellm_payload(user_id, "oi")
    out = run_pre_call(data)
    assert out["metadata"][METADATA_USER_ID_KEY] == user_id


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-User-Id": ""},
        {"X-User-Id": "   "},
        {"X-User-Id": "admin"},
        {"X-User-Id": "Jean"},
        {"X-User-Id": "TATI"},
        {"Authorization": "Bearer x"},
        {"x-user-id": " "},
    ],
)
def test_pre_call_rejects_invalid_or_missing_x_user_id(headers: dict[str, str]) -> None:
    data = make_litellm_payload(None, "oi")
    data["proxy_server_request"]["headers"] = headers
    with pytest.raises(InvalidUserIdError):
        run_pre_call(data)


def test_pre_call_rejects_when_proxy_server_request_headers_missing() -> None:
    data = {"model": "newchat", "messages": [{"role": "user", "content": "oi"}]}
    with pytest.raises(InvalidUserIdError):
        run_pre_call(data)


def test_pre_call_falls_back_to_metadata_headers() -> None:
    """LibreChat pode enviar headers em metadata.headers (sem proxy_server_request)."""
    data = {
        "model": "newchat",
        "messages": [{"role": "user", "content": "oi"}],
        "metadata": {"headers": {"X-User-Id": "jean"}},
    }
    run_pre_call(data)
    assert data["metadata"][METADATA_USER_ID_KEY] == "jean"


@pytest.mark.parametrize("variant", ["x-user-id", "X-User-Id", "X-USER-ID"])
def test_pre_call_accepts_case_insensitive_header(variant: str) -> None:
    data = make_litellm_payload(None, "oi")
    data["proxy_server_request"]["headers"] = {variant: "jean"}
    run_pre_call(data)
    assert data["metadata"][METADATA_USER_ID_KEY] == "jean"


@pytest.mark.parametrize("user_id", ["jean", "tati"])
@pytest.mark.parametrize("whitespace", [" ", "  ", "\t"])
def test_pre_call_strips_whitespace_around_user_id(
    user_id: str, whitespace: str
) -> None:
    """Espaços ao redor do valor são stripados — ' jean ' é válido."""
    data = make_litellm_payload(None, "oi")
    data["proxy_server_request"]["headers"] = {
        "X-User-Id": f"{whitespace}{user_id}{whitespace}"
    }
    run_pre_call(data)
    assert data["metadata"][METADATA_USER_ID_KEY] == user_id


def test_post_call_without_user_id_in_metadata_is_noop(patched_backends) -> None:
    mem0, _ = patched_backends
    data = {"metadata": {}}
    response = make_post_call_response("ok")
    out = run_post_call(data, response)
    assert out is response
    assert mem0.add_calls == []


@pytest.mark.parametrize("bad_user_id", [None, 123, ["jean"]])
def test_post_call_with_non_string_user_id_in_metadata_is_noop(
    bad_user_id: object, patched_backends
) -> None:
    mem0, _ = patched_backends
    data = {
        "metadata": {
            METADATA_USER_ID_KEY: bad_user_id,
            "newchat_conversation": [{"role": "user", "content": "oi"}],
        }
    }
    response = make_post_call_response("ok")
    out = run_post_call(data, response)
    assert out is response
    assert mem0.add_calls == []


def test_post_call_with_empty_string_user_id_in_metadata_is_noop(
    patched_backends,
) -> None:
    mem0, _ = patched_backends
    data = {
        "metadata": {
            METADATA_USER_ID_KEY: "",
            "newchat_conversation": [{"role": "user", "content": "oi"}],
        }
    }
    response = make_post_call_response("ok")
    out = run_post_call(data, response)
    assert out is response
    assert mem0.add_calls == []


def test_pre_call_with_empty_messages_validates_user_id_and_does_not_crash(
    patched_backends,
) -> None:
    mem0, _ = patched_backends
    data = make_litellm_payload("jean", "placeholder")
    data["messages"] = []
    out = run_pre_call(data)
    assert out["metadata"][METADATA_USER_ID_KEY] == "jean"
    assert mem0.search_calls == []


def test_post_call_persists_using_user_id_from_metadata(patched_backends) -> None:
    mem0, _ = patched_backends
    data = make_post_call_payload(
        user_id="tati",
        conversation=[{"role": "user", "content": "Meu nome é Tatiane"}],
    )
    run_post_call(data, make_post_call_response("Anotado!"))

    assert mem0.add_calls, "mem0 add deveria ter sido chamado"
    payload = mem0.add_calls[0]["payload"]
    assert payload["user_id"] == "tati"
    assert payload["infer"] is False
    assert payload["messages"][0]["content"] == "Meu nome é Tatiane"


def test_pre_call_metadata_user_id_must_be_in_allowlist() -> None:
    """Metadata injetado por cliente não bypassa allowlist — header é a fonte."""
    data = make_litellm_payload(None, "oi")
    data["proxy_server_request"]["headers"] = {"X-User-Id": "admin"}
    data["metadata"] = {METADATA_USER_ID_KEY: "jean"}
    with pytest.raises(InvalidUserIdError):
        run_pre_call(data)


def test_custom_callbacks_translate_invalid_user_id_to_http_400() -> None:
    """Handler LiteLLM deve mapear InvalidUserIdError → 400 (ver custom_callbacks)."""
    pytest.importorskip("boto3", reason="custom_callbacks depende de boto3 (transitive)")
    from config.litellm.custom_callbacks import NewChatProxyHandler

    handler = NewChatProxyHandler()
    data = make_litellm_payload(None, "oi")

    import asyncio

    async def _call() -> None:
        await handler.async_pre_call_hook(  # type: ignore[arg-type]
            user_api_key_dict=None,
            cache=None,
            data=data,
            call_type="completion",
        )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_call())
    assert exc_info.value.status_code == 400
    assert "X-User-Id" in str(exc_info.value.detail)
