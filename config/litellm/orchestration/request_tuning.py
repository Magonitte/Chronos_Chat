"""Ajustes de latência no request (cap max_tokens, truncar histórico)."""

from __future__ import annotations

import os
from typing import Any, Mapping, Sequence

from orchestration.types import ChatMessage

DEFAULT_MAX_OUTPUT_TOKENS = 1536
DEFAULT_MAX_CONTEXT_MESSAGES = 6


def _env_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key, "").strip().lower()
    if not raw:
        return default
    return raw not in ("false", "0", "no", "off")


def apply_max_tokens_cap(
    data: dict[str, Any],
    environ: Mapping[str, str] | None = None,
) -> None:
    """Limita max_tokens do request (LiteLLM → llama.cpp)."""
    env = environ if environ is not None else os.environ
    cap = _env_int(env, "NEWCHAT_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS)
    if cap <= 0:
        return

    current = data.get("max_tokens")
    if current is None:
        data["max_tokens"] = cap
        return

    try:
        data["max_tokens"] = min(int(current), cap)
    except (TypeError, ValueError):
        data["max_tokens"] = cap


DEFAULT_THINKING_MAX_TOKENS = 3072


def apply_thinking(
    data: dict[str, Any],
    enable: bool,
    environ: Mapping[str, str] | None = None,
) -> None:
    """
    Controla thinking no llama.cpp (Qwen 3.6) baseado na politica.

    enable=True  → ajusta max_tokens para cima (NEWCHAT_THINKING_MAX_TOKENS).
    enable=False → desliga thinking (extra_body.enable_thinking = False).
    """
    env = environ if environ is not None else os.environ

    if enable:
        thinking_tokens = _env_int(env, "NEWCHAT_THINKING_MAX_TOKENS", DEFAULT_THINKING_MAX_TOKENS)
        current = data.get("max_tokens")
        if current is None:
            data["max_tokens"] = thinking_tokens
        else:
            try:
                if int(current) < thinking_tokens:
                    data["max_tokens"] = thinking_tokens
            except (TypeError, ValueError):
                data["max_tokens"] = thinking_tokens
    else:
        extra = data.get("extra_body")
        if not isinstance(extra, dict):
            extra = {}

        kwargs = extra.get("chat_template_kwargs")
        if not isinstance(kwargs, dict):
            kwargs = {}
        kwargs["enable_thinking"] = False
        extra["chat_template_kwargs"] = kwargs
        extra["enable_thinking"] = False
        data["extra_body"] = extra


def apply_generation_params(
    data: dict[str, Any],
    environ: Mapping[str, str] | None = None,
) -> None:
    """Cap de max_tokens (pensando desligado pelo thinking_policy no pre_call)."""
    apply_max_tokens_cap(data, environ)


def truncate_messages_for_context(
    messages: Sequence[ChatMessage],
    *,
    max_messages: int | None = None,
    environ: Mapping[str, str] | None = None,
) -> tuple[ChatMessage, ...]:
    """
    Mantém mensagens system e as últimas N não-system (histórico curto para inferência).

    A conversa completa permanece em metadata para POST-CALL / mem0.
    """
    env = environ if environ is not None else os.environ
    limit = (
        max_messages
        if max_messages is not None
        else _env_int(env, "NEWCHAT_MAX_CONTEXT_MESSAGES", DEFAULT_MAX_CONTEXT_MESSAGES)
    )
    if limit <= 0 or not messages:
        return tuple(messages)

    system_msgs = [m for m in messages if m.role == "system"]
    non_system = [m for m in messages if m.role != "system"]
    if len(non_system) <= limit:
        return tuple(messages)

    tail = non_system[-limit:]
    if system_msgs:
        return tuple(system_msgs) + tuple(tail)
    return tuple(tail)


def apply_disable_thinking(
    data: dict[str, Any],
    environ: Mapping[str, str] | None = None,
) -> None:
    """Deprecated. Use apply_thinking(data, enable=False, environ=environ)."""
    apply_thinking(data, False, environ)
