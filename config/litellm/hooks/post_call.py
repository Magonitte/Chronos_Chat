"""POST-CALL fino: persiste memória via mem0 quando memory_policy aprova."""

from __future__ import annotations

from typing import Any

from hooks.observability import log_event, request_id_from_metadata
from hooks.pre_call import (
    METADATA_CONVERSATION_KEY,
    METADATA_MEMORY_TEXTS_KEY,
    METADATA_RAG_TRIGGERED_KEY,
    METADATA_USER_ID_KEY,
)
from orchestration import mem0_client
from orchestration.memory_policy import (
    MemoryPersistContext,
    direct_memory_text,
    should_persist,
)
from orchestration.thinking_response import extract_visible_assistant_text, normalize_assistant_response
from orchestration.types import ChatMessage


def _lite_to_domain(messages: Any) -> tuple[ChatMessage, ...]:
    if not isinstance(messages, list):
        return ()
    out: list[ChatMessage] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "user"))
        content = item.get("content", "")
        out.append(ChatMessage(role=role, content=content))
    return tuple(out)


def _extract_assistant_response(response: Any) -> str:
    if isinstance(response, dict):
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    reasoning = message.get("reasoning_content")
                    visible = extract_visible_assistant_text(
                        content if isinstance(content, str) else None,
                        reasoning if isinstance(reasoning, str) else None,
                    )
                    if visible:
                        return visible
    if hasattr(response, "choices") and response.choices:
        choice = response.choices[0]
        message = getattr(choice, "message", None)
        if message is not None:
            content = getattr(message, "content", None)
            reasoning = getattr(message, "reasoning_content", None)
            visible = extract_visible_assistant_text(
                content if isinstance(content, str) else None,
                reasoning if isinstance(reasoning, str) else None,
            )
            if visible:
                return visible
    return ""


def run_post_call(data: dict[str, Any], response: Any) -> Any:
    """
    Pós-processamento: memory_policy + mem0_client.add async (fail-open).

    Normaliza content vazio (thinking) antes de devolver ao LibreChat.
    """
    response = normalize_assistant_response(response)

    meta = data.get("metadata")
    request_id = request_id_from_metadata(meta if isinstance(meta, dict) else None)

    if not isinstance(meta, dict):
        log_event(
            "post_call_skip",
            request_id=request_id,
            reason="metadata_missing",
        )
        return response

    user_id = meta.get(METADATA_USER_ID_KEY)
    if not isinstance(user_id, str) or not user_id:
        log_event(
            "post_call_skip",
            request_id=request_id,
            reason="user_id_missing",
        )
        return response

    conversation = _lite_to_domain(meta.get(METADATA_CONVERSATION_KEY))
    memory_texts_raw = meta.get(METADATA_MEMORY_TEXTS_KEY)
    existing_texts: tuple[str, ...] = ()
    if isinstance(memory_texts_raw, list):
        existing_texts = tuple(str(t) for t in memory_texts_raw if t)

    ctx = MemoryPersistContext(
        user_id=user_id,
        rag_was_triggered=bool(meta.get(METADATA_RAG_TRIGGERED_KEY, False)),
        existing_memory_texts=existing_texts,
    )

    direct_text = direct_memory_text(conversation, ctx)
    if direct_text:
        mem0_client.add_direct_async(user_id, direct_text)
        log_event(
            "post_call_complete",
            request_id=request_id,
            user_id=user_id,
            persist="direct",
            rag_triggered=ctx.rag_was_triggered,
        )
        return response

    assistant_text = _extract_assistant_response(response)
    if should_persist(conversation, assistant_text or "", ctx):
        if assistant_text:
            messages_for_add = conversation + (
                ChatMessage(role="assistant", content=assistant_text),
            )
            mem0_client.add_async(user_id, messages_for_add)
            log_event(
                "post_call_complete",
                request_id=request_id,
                user_id=user_id,
                persist="async",
                rag_triggered=ctx.rag_was_triggered,
            )
        else:
            log_event(
                "post_call_complete",
                request_id=request_id,
                user_id=user_id,
                persist="skipped_empty_assistant",
                rag_triggered=ctx.rag_was_triggered,
            )
    else:
        log_event(
            "post_call_complete",
            request_id=request_id,
            user_id=user_id,
            persist="none",
            rag_triggered=ctx.rag_was_triggered,
        )

    return response
