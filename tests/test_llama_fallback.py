"""Testes de detecção llama offline e mensagem ao usuário (T8.2)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from hooks.llama_fallback import (
    LLAMA_OFFLINE_USER_MESSAGE,
    build_llama_offline_http_exception,
    is_llama_unreachable,
    llama_offline_from_failure,
)


def test_is_llama_unreachable_connection_error() -> None:
    assert is_llama_unreachable(ConnectionRefusedError(111, "Connection refused"))


def test_is_llama_unreachable_message_marker() -> None:
    assert is_llama_unreachable(
        RuntimeError("litellm.APIConnectionError: Connection error. host.docker.internal:8080")
    )


def test_is_llama_unreachable_unrelated() -> None:
    assert not is_llama_unreachable(ValueError("invalid model name"))


def test_build_llama_offline_http_exception_openai_shape() -> None:
    exc = build_llama_offline_http_exception(request_id="req-99")
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 503
    assert isinstance(exc.detail, dict)
    err = exc.detail["error"]
    assert LLAMA_OFFLINE_USER_MESSAGE in err["message"]
    assert "req-99" in err["message"]
    assert err["code"] == "llama_server_offline"


def test_llama_offline_from_failure_returns_none_for_other_errors() -> None:
    assert llama_offline_from_failure(ValueError("bad"), {"metadata": {}}) is None


def test_llama_offline_from_failure_with_connection() -> None:
    request_data = {
        "metadata": {"newchat_request_id": "hook-req-1"},
        "litellm_call_id": "litellm-1",
    }
    result = llama_offline_from_failure(
        ConnectionError("failed to connect to host.docker.internal:8080"),
        request_data,
    )
    assert isinstance(result, HTTPException)
    assert result.status_code == 503
    assert "hook-req-1" in result.detail["error"]["message"]


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(
            __import__("litellm.exceptions", fromlist=["APIConnectionError"]).APIConnectionError(
                message="Connection error",
                llm_provider="openai",
                model="qwen",
            ),
            id="litellm_api_connection",
        )
    ],
)
def test_is_llama_unreachable_litellm_exception(exc: BaseException) -> None:
    assert is_llama_unreachable(exc)
