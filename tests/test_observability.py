"""Testes de logs estruturados e request_id (T8.2)."""

from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest

from hooks import observability
from hooks.observability import (
    METADATA_REQUEST_ID_KEY,
    log_event,
    resolve_request_id,
    timed_call,
)


@pytest.fixture
def hook_log_lines() -> list[str]:
    """Captura linhas JSON do logger newchat.hooks (propagate=False)."""
    lines: list[str] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(record.getMessage())

    handler = _Collect()
    logger = observability._LOGGER
    logger.addHandler(handler)
    yield lines
    logger.removeHandler(handler)
from hooks.pre_call import METADATA_USER_ID_KEY, run_pre_call


def test_resolve_request_id_from_header() -> None:
    data = {"proxy_server_request": {"headers": {"X-Request-Id": "req-abc-123"}}}
    assert resolve_request_id(data) == "req-abc-123"


def test_resolve_request_id_from_litellm_call_id() -> None:
    data = {"litellm_call_id": "litellm-uuid-1"}
    assert resolve_request_id(data) == "litellm-uuid-1"


def test_timed_call_measures_duration() -> None:
    import time

    with timed_call() as bucket:
        time.sleep(0.01)
    assert bucket[0] >= 5.0


def test_log_event_emits_json(hook_log_lines: list[str]) -> None:
    log_event("test_event", request_id="r1", user_id="jean", mem0_ms=12.5)
    assert hook_log_lines
    payload = json.loads(hook_log_lines[-1])
    assert payload["event"] == "test_event"
    assert payload["request_id"] == "r1"
    assert payload["user_id"] == "jean"
    assert payload["mem0_ms"] == 12.5


def test_pre_call_logs_structured_fields(hook_log_lines: list[str]) -> None:
    data = {
        "messages": [{"role": "user", "content": "Qual meu nome?"}],
        "proxy_server_request": {
            "headers": {"X-User-Id": "jean", "X-Request-Id": "pre-req-1"},
        },
    }

    with patch("hooks.pre_call.mem0_client.search", return_value=()):
        with patch("hooks.pre_call.rag_client.retrieve", return_value=()):
            run_pre_call(data)

    assert data["metadata"][METADATA_REQUEST_ID_KEY] == "pre-req-1"
    assert data["metadata"][METADATA_USER_ID_KEY] == "jean"

    pre_logs = [ln for ln in hook_log_lines if "pre_call_complete" in ln]
    assert pre_logs
    payload = json.loads(pre_logs[-1])
    assert payload["request_id"] == "pre-req-1"
    assert payload["user_id"] == "jean"
    assert "mem0_ms" in payload
    assert "rag_ms" in payload
