"""Testes dos hooks PRE/POST (sem import litellm nos hooks)."""

import os
from unittest.mock import patch

import pytest

from hooks.post_call import run_post_call
from hooks.pre_call import METADATA_USER_ID_KEY, run_pre_call
from orchestration.types import ChatMessage, Memory
from orchestration.user_id import InvalidUserIdError


def _data_with_headers(headers: dict[str, str]) -> dict:
    return {
        "model": "newchat",
        "messages": [{"role": "user", "content": "oi"}],
        "proxy_server_request": {"headers": headers},
    }


@pytest.fixture(autouse=True)
def _mock_mem0_search():
    with patch(
        "hooks.pre_call.mem0_client.search",
        return_value=(),
    ):
        yield


@pytest.mark.parametrize("user_id", ["jean", "tati"])
def test_run_pre_call_accepts_valid_x_user_id(user_id: str) -> None:
    data = _data_with_headers({"X-User-Id": user_id})
    out = run_pre_call(data)
    assert out is data
    assert data["metadata"][METADATA_USER_ID_KEY] == user_id


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-User-Id": ""},
        {"X-User-Id": "admin"},
    ],
)
def test_run_pre_call_rejects_invalid_x_user_id(headers: dict[str, str]) -> None:
    with pytest.raises(InvalidUserIdError):
        run_pre_call(_data_with_headers(headers))


def test_run_pre_call_reads_headers_from_metadata() -> None:
    data = {
        "messages": [],
        "metadata": {"headers": {"x-user-id": "jean"}},
    }
    run_pre_call(data)
    assert data["metadata"][METADATA_USER_ID_KEY] == "jean"


def test_run_pre_call_injects_memories_into_system_prompt() -> None:
    data = _data_with_headers({"X-User-Id": "jean"})
    data["messages"] = [{"role": "user", "content": "Qual meu nome?"}]

    with patch(
        "hooks.pre_call.mem0_client.search",
        return_value=(Memory(id="m1", text="Meu nome é Jean", score=0.95),),
    ):
        run_pre_call(data)

    assert data["messages"][0]["role"] == "system"
    assert "Memórias do usuário" in data["messages"][0]["content"]
    assert "Jean" in data["messages"][0]["content"]


def test_run_pre_call_search_uses_user_id() -> None:
    data = _data_with_headers({"X-User-Id": "tati"})
    data["messages"] = [{"role": "user", "content": "teste isolamento"}]

    with patch("hooks.pre_call.mem0_client.search", return_value=()) as mock_search:
        run_pre_call(data)
        mock_search.assert_called_once()
        assert mock_search.call_args[0][0] == "tati"


def test_run_post_call_returns_response_unchanged() -> None:
    data = {"metadata": {METADATA_USER_ID_KEY: "jean"}}
    response = {"choices": [{"message": {"content": "ok"}}]}
    assert run_post_call(data, response) is response


def test_run_post_call_persists_when_policy_approves() -> None:
    data = {
        "metadata": {
            METADATA_USER_ID_KEY: "jean",
            "newchat_conversation": [
                {"role": "user", "content": "Eu prefiro café com leite"},
            ],
            "newchat_memory_texts": [],
            "newchat_rag_triggered": False,
        }
    }
    response = {"choices": [{"message": {"content": "Entendi sua preferência."}}]}

    with patch("hooks.post_call.mem0_client.add_direct_async") as mock_direct:
        with patch("hooks.post_call.mem0_client.add_async") as mock_add:
            run_post_call(data, response)
            mock_direct.assert_called_once()
            assert mock_direct.call_args[0][0] == "jean"
            assert mock_direct.call_args[0][1] == "Eu prefiro café com leite"
            mock_add.assert_not_called()


def test_run_pre_call_skips_mem0_search_on_trivial() -> None:
    data = _data_with_headers({"X-User-Id": "tati"})
    data["messages"] = [{"role": "user", "content": "oi"}]

    with patch("hooks.pre_call.mem0_client.search") as mock_search:
        run_pre_call(data)
        mock_search.assert_not_called()


def test_run_pre_call_applies_max_tokens_cap() -> None:
    data = _data_with_headers({"X-User-Id": "jean"})
    data["max_tokens"] = 8000

    with patch.dict("os.environ", {"NEWCHAT_MAX_OUTPUT_TOKENS": "1536"}):
        run_pre_call(data)

    assert data["max_tokens"] == 1536


def test_run_pre_call_applies_disable_thinking() -> None:
    data = _data_with_headers({"X-User-Id": "jean"})
    run_pre_call(data)
    assert data["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False


def test_run_post_call_uses_direct_for_explicit_remember() -> None:
    data = {
        "metadata": {
            METADATA_USER_ID_KEY: "tati",
            "newchat_conversation": [
                {
                    "role": "user",
                    "content": "Lembre que o nome de minha mãe é Gertrudes",
                },
            ],
            "newchat_memory_texts": [],
            "newchat_rag_triggered": False,
        }
    }
    response = {"choices": [{"message": {"content": "Entendido!"}}]}

    with patch("hooks.post_call.mem0_client.add_direct_async") as mock_direct:
        with patch("hooks.post_call.mem0_client.add_async") as mock_add:
            run_post_call(data, response)
            mock_direct.assert_called_once()
            mock_add.assert_not_called()


def test_run_post_call_skips_when_policy_rejects() -> None:
    data = {
        "metadata": {
            METADATA_USER_ID_KEY: "jean",
            "newchat_conversation": [{"role": "user", "content": "oi"}],
            "newchat_memory_texts": [],
        }
    }
    response = {"choices": [{"message": {"content": "Olá!"}}]}

    with patch("hooks.post_call.mem0_client.add_async") as mock_add:
        run_post_call(data, response)
        mock_add.assert_not_called()
