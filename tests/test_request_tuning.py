"""Testes de request_tuning (cap max_tokens, truncar histórico)."""

from orchestration.request_tuning import (
    apply_max_tokens_cap,
    apply_thinking,
    truncate_messages_for_context,
)
from orchestration.types import ChatMessage


def test_apply_max_tokens_cap_when_missing() -> None:
    data: dict = {}
    apply_max_tokens_cap(data, {"NEWCHAT_MAX_OUTPUT_TOKENS": "512"})
    assert data["max_tokens"] == 512


def test_apply_max_tokens_cap_lowers_high_value() -> None:
    data = {"max_tokens": 4096}
    apply_max_tokens_cap(data, {"NEWCHAT_MAX_OUTPUT_TOKENS": "1024"})
    assert data["max_tokens"] == 1024


def test_apply_max_tokens_cap_keeps_lower_value() -> None:
    data = {"max_tokens": 256}
    apply_max_tokens_cap(data, {"NEWCHAT_MAX_OUTPUT_TOKENS": "1024"})
    assert data["max_tokens"] == 256


def test_truncate_messages_keeps_system_and_tail() -> None:
    msgs = (
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="user", content="u1"),
        ChatMessage(role="assistant", content="a1"),
        ChatMessage(role="user", content="u2"),
        ChatMessage(role="assistant", content="a2"),
        ChatMessage(role="user", content="u3"),
        ChatMessage(role="assistant", content="a3"),
    )
    out = truncate_messages_for_context(msgs, max_messages=2)
    assert out[0].role == "system"
    assert len(out) == 3
    assert out[-1].content == "a3"


def test_apply_thinking_false_sets_extra_body() -> None:
    data: dict = {}
    apply_thinking(data, False, {"NEWCHAT_DISABLE_THINKING": "true"})
    assert data["extra_body"]["enable_thinking"] is False
    assert data["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False


def test_apply_thinking_true_does_not_set_disable() -> None:
    data: dict = {}
    apply_thinking(data, True, {"NEWCHAT_THINKING_MAX_TOKENS": "3072"})
    extra = data.get("extra_body", {})
    assert extra.get("enable_thinking") is not False


def test_apply_thinking_true_increases_max_tokens() -> None:
    data = {"max_tokens": 1024}
    apply_thinking(data, True, {"NEWCHAT_THINKING_MAX_TOKENS": "3072"})
    assert data["max_tokens"] == 3072


def test_apply_thinking_true_respects_higher_cap() -> None:
    data = {"max_tokens": 4096}
    apply_thinking(data, True, {"NEWCHAT_THINKING_MAX_TOKENS": "3072"})
    assert data["max_tokens"] == 4096


def test_apply_thinking_true_sets_missing_max_tokens() -> None:
    data: dict = {}
    apply_thinking(data, True, {"NEWCHAT_THINKING_MAX_TOKENS": "3072"})
    assert data["max_tokens"] == 3072
