"""Normaliza respostas Qwen thinking → content visível para o LibreChat."""

from __future__ import annotations

from typing import Any

# Qwen / llama.cpp (evita tags literais no source por sanitização de editor)
_THINK_CLOSE_MARKERS = (
    "\u003c/" + "redacted_thinking" + "\u003e",
    "\u003c/" + "think" + "\u003e",
)


def _after_thinking_tag(text: str) -> str:
    lowered = text.lower()
    for marker in _THINK_CLOSE_MARKERS:
        idx = lowered.find(marker.lower())
        if idx < 0:
            continue
        tail = text[idx + len(marker) :].strip()
        if tail:
            return tail
    return ""


def extract_visible_assistant_text(content: str | None, reasoning: str | None) -> str:
    """Obtém texto de resposta quando content veio vazio (thinking consumiu max_tokens)."""
    if isinstance(content, str) and content.strip():
        return content.strip()

    if not isinstance(reasoning, str) or not reasoning.strip():
        return ""

    return _after_thinking_tag(reasoning)


def _normalize_message_dict(message: dict[str, Any]) -> None:
    content = message.get("content")
    reasoning = message.get("reasoning_content")
    visible = extract_visible_assistant_text(
        content if isinstance(content, str) else None,
        reasoning if isinstance(reasoning, str) else None,
    )
    if visible and (not isinstance(content, str) or not content.strip()):
        message["content"] = visible


def normalize_assistant_response(response: Any) -> Any:
    """
    Garante content preenchido quando o backend só retornou reasoning_content.

    Necessário para Qwen 3.6 + thinking=1 com max_tokens baixo.
    """
    if isinstance(response, dict):
        choices = response.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if isinstance(choice, dict):
                    message = choice.get("message")
                    if isinstance(message, dict):
                        _normalize_message_dict(message)
        return response

    choices = getattr(response, "choices", None)
    if choices:
        for choice in choices:
            message = getattr(choice, "message", None)
            if message is None:
                continue
            content = getattr(message, "content", None)
            reasoning = getattr(message, "reasoning_content", None)
            visible = extract_visible_assistant_text(
                content if isinstance(content, str) else None,
                reasoning if isinstance(reasoning, str) else None,
            )
            if visible and (not isinstance(content, str) or not content.strip()):
                if hasattr(message, "content"):
                    message.content = visible
                else:
                    setattr(message, "content", visible)

    return response
