"""PRE-CALL fino: valida X-User-Id, busca mem0 e monta contexto."""

from __future__ import annotations

from typing import Any

from hooks.observability import (
    ensure_request_id_in_metadata,
    log_event,
    resolve_request_id,
    timed_call,
)
from hooks.request_headers import extract_request_headers
from orchestration import context_builder
from orchestration import mem0_client
from orchestration import rag_client
from orchestration.memory_policy import is_system_request, should_skip_mem0_search
from orchestration.rag_policy import should_trigger
from orchestration.request_tuning import apply_generation_params, truncate_messages_for_context
from orchestration.types import ChatMessage, OrchestrationRequest, RagChunk, UserContext
from orchestration.user_id import extract_user_id

METADATA_USER_ID_KEY = "newchat_user_id"
METADATA_CONVERSATION_KEY = "newchat_conversation"
METADATA_MEMORY_TEXTS_KEY = "newchat_memory_texts"
METADATA_RAG_TRIGGERED_KEY = "newchat_rag_triggered"
METADATA_RAG_ENABLED_KEY = "newchat_rag_enabled"
METADATA_ACTIVE_WORKSPACE_KEY = "newchat_active_workspace"

_BASE_SYSTEM_PROMPT = (
    "Você é um assistente pessoal local e privado. "
    "Responda sempre em português do Brasil, de forma natural e conversacional. "
    "Utilize as memórias do usuário de forma natural na conversa, "
    "sem listar nem reproduzir o formato bruto das memórias. "
    "Quando o usuário pedir para lembrar algo, confirme de forma breve e natural."
)


def _messages_to_domain(messages: list[Any]) -> tuple[ChatMessage, ...]:
    out: list[ChatMessage] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "user"))
        content = item.get("content", "")
        out.append(ChatMessage(role=role, content=content))
    return tuple(out)


def _domain_message_to_lite(msg: ChatMessage) -> dict[str, Any]:
    return {"role": msg.role, "content": msg.content}


def _has_images(messages: list[Any]) -> bool:
    for item in messages:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                return True
    return False


def _user_context_from_metadata(user_id: str, meta: dict[str, Any]) -> UserContext:
    rag_enabled = meta.get(METADATA_RAG_ENABLED_KEY, True)
    if isinstance(rag_enabled, str):
        rag_enabled = rag_enabled.strip().lower() not in ("false", "0", "no", "off")
    active_ws = meta.get(METADATA_ACTIVE_WORKSPACE_KEY)
    if not isinstance(active_ws, str) or not active_ws.strip():
        active_ws = None
    else:
        active_ws = active_ws.strip()
    return UserContext(
        user_id=user_id,
        rag_enabled=bool(rag_enabled),
        active_workspace=active_ws,
    )


def run_pre_call(data: dict[str, Any]) -> dict[str, Any]:
    """
    Valida X-User-Id (fail-closed), mem0 sempre, RAG só se rag_policy.should_trigger.
    """
    headers = extract_request_headers(data)
    user_id = extract_user_id(headers)
    request_id = resolve_request_id(data, headers)
    ensure_request_id_in_metadata(data, request_id)

    messages_raw = data.get("messages") or []
    if not isinstance(messages_raw, list):
        messages_raw = []

    domain_messages_full = _messages_to_domain(messages_raw)
    domain_messages_ctx = truncate_messages_for_context(domain_messages_full)

    _ = OrchestrationRequest.from_messages(
        user_id=user_id,
        messages=domain_messages_ctx,
        model=data.get("model") if isinstance(data.get("model"), str) else None,
        has_images=_has_images(messages_raw),
    )

    apply_generation_params(data)

    meta = data.get("metadata")
    if not isinstance(meta, dict):
        meta = {}
        data["metadata"] = meta

    # Requisições internas do cliente (ex: geração de título do LibreChat):
    # não injetar memórias nem system prompt — apenas encaminhar como está.
    if is_system_request(domain_messages_ctx):
        meta[METADATA_USER_ID_KEY] = user_id
        meta[METADATA_CONVERSATION_KEY] = [_domain_message_to_lite(m) for m in domain_messages_full]
        meta[METADATA_MEMORY_TEXTS_KEY] = []
        meta[METADATA_RAG_TRIGGERED_KEY] = False
        log_event(
            "pre_call_complete",
            request_id=request_id,
            user_id=user_id,
            system_request=True,
            mem0_ms=0.0,
            rag_ms=0.0,
            mem0_count=0,
            rag_chunks=0,
            rag_triggered=False,
        )
        return data

    query = mem0_client.extract_search_query(domain_messages_ctx)
    mem0_ms = 0.0
    if should_skip_mem0_search(domain_messages_ctx):
        memories: tuple = ()
    else:
        with timed_call() as mem0_bucket:
            memories = mem0_client.search(user_id, query)
        mem0_ms = mem0_bucket[0]

    user_ctx = _user_context_from_metadata(user_id, meta)
    rag_triggered = should_trigger(query, user_ctx)
    rag_chunks: tuple[RagChunk, ...] = ()
    rag_ms = 0.0
    if rag_triggered:
        with timed_call() as rag_bucket:
            rag_chunks = rag_client.retrieve(user_id, query)
        rag_ms = rag_bucket[0]

    built = context_builder.build(
        messages=domain_messages_ctx,
        memories=memories,
        rag_chunks=rag_chunks,
        rag_active=rag_triggered,
        base_system_prompt=_BASE_SYSTEM_PROMPT,
    )

    data["messages"] = [_domain_message_to_lite(m) for m in built.messages]

    meta[METADATA_USER_ID_KEY] = user_id
    meta[METADATA_CONVERSATION_KEY] = [
        _domain_message_to_lite(m) for m in domain_messages_full
    ]
    meta[METADATA_MEMORY_TEXTS_KEY] = [m.text for m in built.memories_used]
    meta[METADATA_RAG_TRIGGERED_KEY] = rag_triggered

    log_event(
        "pre_call_complete",
        request_id=request_id,
        user_id=user_id,
        system_request=False,
        mem0_ms=round(mem0_ms, 2),
        rag_ms=round(rag_ms, 2),
        mem0_count=len(memories),
        rag_chunks=len(rag_chunks),
        rag_triggered=rag_triggered,
    )

    return data
