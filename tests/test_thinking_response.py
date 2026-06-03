"""Testes de normalização Qwen thinking → content."""

from orchestration.thinking_response import (
    extract_visible_assistant_text,
    normalize_assistant_response,
)
from orchestration.request_tuning import apply_disable_thinking, apply_generation_params


def test_extract_visible_prefers_content() -> None:
    assert extract_visible_assistant_text("Resposta.", "raciocínio") == "Resposta."


def test_extract_visible_from_reasoning_after_think_tag() -> None:
    reasoning = "analise...\u003c/redacted_thinking\u003e\nMinha mãe é Gertrudes."
    assert extract_visible_assistant_text("", reasoning) == "Minha mãe é Gertrudes."


def test_normalize_assistant_response_fills_empty_content() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "reasoning_content": "ok\u003c/think\u003e\nOlá!",
                }
            }
        ]
    }
    out = normalize_assistant_response(response)
    assert out["choices"][0]["message"]["content"] == "Olá!"


def test_apply_disable_thinking_sets_extra_body() -> None:
    data: dict = {}
    apply_disable_thinking(data, {"NEWCHAT_DISABLE_THINKING": "true"})
    assert data["extra_body"]["enable_thinking"] is False
    assert data["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False


def test_apply_generation_params_combines_cap_and_thinking() -> None:
    data = {"max_tokens": 8000}
    apply_generation_params(data, {"NEWCHAT_MAX_OUTPUT_TOKENS": "1536", "NEWCHAT_DISABLE_THINKING": "true"})
    assert data["max_tokens"] == 1536
    assert data["extra_body"]["enable_thinking"] is False
