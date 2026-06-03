"""Testes do mem0_client (HTTP mockado, fail-open)."""

from unittest.mock import patch

from orchestration.mem0_client import (
    Mem0ClientConfig,
    add,
    add_async,
    add_direct,
    add_direct_async,
    extract_search_query,
    load_config,
    search,
)
from orchestration.types import ChatMessage


def test_load_config_from_env() -> None:
    cfg = load_config(
        {
            "MEM0_API_URL": "http://mem0:9000",
            "MEM0_TIMEOUT": "3",
            "MEM0_ADD_TIMEOUT": "90",
            "MEM0_SEARCH_LIMIT": "5",
            "MEM0_MIN_SCORE": "0.4",
        }
    )
    assert cfg.api_url == "http://mem0:9000"
    assert cfg.timeout == 3.0
    assert cfg.add_timeout == 90.0
    assert cfg.search_limit == 5
    assert cfg.min_score == 0.4


def test_extract_search_query_last_user_messages() -> None:
    messages = (
        ChatMessage(role="user", content="primeira"),
        ChatMessage(role="assistant", content="ok"),
        ChatMessage(role="user", content="segunda pergunta"),
    )
    assert extract_search_query(messages) == "primeira segunda pergunta"


def test_search_filters_by_min_score() -> None:
    cfg = Mem0ClientConfig(
        api_url="http://mem0:8000",
        timeout=2.0,
        add_timeout=120.0,
        search_limit=5,
        min_score=0.35,
    )

    def fake_post(url: str, payload: dict, timeout: float) -> dict:
        return {
            "results": [
                {"id": "a", "memory": "alta", "score": 0.9},
                {"id": "b", "memory": "baixa", "score": 0.2},
            ]
        }

    memories = search("jean", "mae", config=cfg, post_json=fake_post)
    assert len(memories) == 1
    assert memories[0].text == "alta"


def test_search_parses_results_and_user_id() -> None:
    cfg = Mem0ClientConfig(
        api_url="http://mem0:8000",
        timeout=2.0,
        add_timeout=120.0,
        search_limit=10,
        min_score=0.0,
    )
    captured: list[dict] = []

    def fake_post(url: str, payload: dict, timeout: float) -> dict:
        captured.append({"url": url, "payload": payload, "timeout": timeout})
        return {
            "results": [
                {"id": "a1", "memory": "Gosta de café", "score": 0.9},
                {"id": "a2", "text": "Mora em SP", "score": 0.7},
            ]
        }

    memories = search("jean", "café", config=cfg, post_json=fake_post)
    assert len(memories) == 2
    assert memories[0].text == "Gosta de café"
    assert memories[0].score == 0.9
    assert captured[0]["url"] == "http://mem0:8000/search"
    assert captured[0]["payload"]["user_id"] == "jean"
    assert captured[0]["payload"]["query"] == "café"
    assert captured[0]["timeout"] == 2.0


def test_search_fail_open_on_error() -> None:
    cfg = Mem0ClientConfig(
        api_url="http://mem0:8000",
        timeout=2.0,
        add_timeout=120.0,
        search_limit=10,
        min_score=0.0,
    )

    def fail_post(url: str, payload: dict, timeout: float) -> None:
        return None

    assert search("tati", "oi", config=cfg, post_json=fail_post) == ()


def test_search_empty_query_returns_empty() -> None:
    cfg = Mem0ClientConfig(
        api_url="http://mem0:8000",
        timeout=2.0,
        add_timeout=120.0,
        search_limit=10,
        min_score=0.0,
    )

    def should_not_call(url: str, payload: dict, timeout: float) -> dict:
        raise AssertionError("should not call mem0")

    assert search("jean", "", config=cfg, post_json=should_not_call) == ()


def test_add_uses_add_timeout() -> None:
    cfg = Mem0ClientConfig(
        api_url="http://mem0:8000",
        timeout=2.0,
        add_timeout=120.0,
        search_limit=10,
        min_score=0.0,
    )
    captured: list[float] = []

    def fake_post(url: str, payload: dict, timeout: float) -> dict:
        captured.append(timeout)
        return {"results": []}

    msgs = (ChatMessage(role="user", content="Eu prefiro Python"),)
    add("jean", msgs, config=cfg, post_json=fake_post)
    assert captured[0] == 120.0


def test_add_posts_messages_with_user_id() -> None:
    cfg = Mem0ClientConfig(
        api_url="http://mem0:8000",
        timeout=2.0,
        add_timeout=120.0,
        search_limit=10,
        min_score=0.0,
    )
    captured: list[dict] = []

    def fake_post(url: str, payload: dict, timeout: float) -> dict:
        captured.append({"url": url, "payload": payload})
        return {"results": []}

    msgs = (
        ChatMessage(role="user", content="Eu prefiro Python"),
        ChatMessage(role="assistant", content="Anotado!"),
    )
    add("jean", msgs, config=cfg, post_json=fake_post)
    assert captured[0]["url"] == "http://mem0:8000/memories"
    assert captured[0]["payload"]["user_id"] == "jean"
    assert len(captured[0]["payload"]["messages"]) == 2


def test_add_async_spawns_thread() -> None:
    cfg = Mem0ClientConfig(
        api_url="http://mem0:8000",
        timeout=2.0,
        add_timeout=120.0,
        search_limit=10,
        min_score=0.0,
    )
    called = {"user_id": None}

    def fake_add(user_id: str, messages, **kwargs) -> None:
        called["user_id"] = user_id

    msgs = (ChatMessage(role="user", content="Lembre que eu gosto de jazz"),)
    with patch("orchestration.mem0_client.add", side_effect=fake_add) as mock_add:
        add_async("tati", msgs, config=cfg)
        import time

        deadline = time.time() + 2.0
        while time.time() < deadline and not mock_add.called:
            time.sleep(0.05)
        assert mock_add.called
        assert called["user_id"] == "tati"


def test_add_direct_uses_infer_false() -> None:
    cfg = Mem0ClientConfig(
        api_url="http://mem0:8000",
        timeout=2.0,
        add_timeout=120.0,
        search_limit=10,
        min_score=0.0,
    )
    captured: list[dict] = []

    def fake_post(url: str, payload: dict, timeout: float) -> dict:
        captured.append({"url": url, "payload": payload, "timeout": timeout})
        return {"results": [{"id": "x", "memory": payload["messages"][0]["content"]}]}

    add_direct("tati", "O nome da mae e Gertrudes", config=cfg, post_json=fake_post)
    assert captured[0]["payload"]["infer"] is False
    assert captured[0]["payload"]["user_id"] == "tati"
    assert captured[0]["timeout"] == 120.0


def test_add_direct_async_spawns_thread() -> None:
    cfg = Mem0ClientConfig(
        api_url="http://mem0:8000",
        timeout=2.0,
        add_timeout=120.0,
        search_limit=10,
        min_score=0.0,
    )

    with patch("orchestration.mem0_client.add_direct") as mock_add:
        add_direct_async("tati", "Eu gosto de jazz", config=cfg)
        import time

        deadline = time.time() + 2.0
        while time.time() < deadline and not mock_add.called:
            time.sleep(0.05)
        assert mock_add.called
