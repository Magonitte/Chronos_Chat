"""Cliente HTTP mem0 — search/add com timeout fail-open (orquestração pura)."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from orchestration.memory_policy import message_text
from orchestration.types import ChatMessage, Memory

logger = logging.getLogger(__name__)

DEFAULT_MEM0_API_URL = "http://mem0:8000"
DEFAULT_MEM0_TIMEOUT = 5.0
DEFAULT_MEM0_ADD_TIMEOUT = 120.0
DEFAULT_SEARCH_LIMIT = 5
DEFAULT_MIN_SCORE = 0.35

PostJsonFn = Callable[[str, dict[str, Any], float], dict[str, Any] | None]


@dataclass(frozen=True)
class Mem0ClientConfig:
    api_url: str
    timeout: float
    add_timeout: float
    search_limit: int
    min_score: float


def _env_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_config(environ: Mapping[str, str] | None = None) -> Mem0ClientConfig:
    env = environ if environ is not None else os.environ
    api_url = env.get("MEM0_API_URL", DEFAULT_MEM0_API_URL).strip() or DEFAULT_MEM0_API_URL
    search_timeout = _env_float(env, "MEM0_TIMEOUT", DEFAULT_MEM0_TIMEOUT)
    add_timeout = _env_float(env, "MEM0_ADD_TIMEOUT", DEFAULT_MEM0_ADD_TIMEOUT)
    return Mem0ClientConfig(
        api_url=api_url.rstrip("/"),
        timeout=search_timeout,
        add_timeout=add_timeout,
        search_limit=_env_int(env, "MEM0_SEARCH_LIMIT", DEFAULT_SEARCH_LIMIT),
        min_score=_env_float(env, "MEM0_MIN_SCORE", DEFAULT_MIN_SCORE),
    )


def extract_search_query(
    messages: Sequence[ChatMessage],
    *,
    max_messages: int = 3,
) -> str:
    """Query para busca mem0: últimas mensagens user (docs/memory-flow.md)."""
    user_texts = [message_text(m) for m in messages if m.role == "user" and message_text(m)]
    if not user_texts:
        return ""
    return " ".join(user_texts[-max_messages:])


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any] | None:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
        logger.error("mem0 request failed url=%s error=%s", url, exc)
        return None


def _parse_search_results(data: dict[str, Any]) -> tuple[Memory, ...]:
    raw_results = data.get("results")
    if not isinstance(raw_results, list):
        return ()

    memories: list[Memory] = []
    for idx, item in enumerate(raw_results):
        if not isinstance(item, dict):
            continue
        text = item.get("memory") or item.get("text") or item.get("content")
        if not text:
            continue
        mem_id = str(item.get("id") or f"mem-{idx}")
        score_raw = item.get("score", 0.0)
        try:
            score = float(score_raw)
        except (TypeError, ValueError):
            score = 0.0
        memories.append(Memory(id=mem_id, text=str(text), score=score, metadata=item))
    return tuple(memories)


def _message_to_api(msg: ChatMessage) -> dict[str, Any]:
    return {"role": msg.role, "content": msg.content}


def _filter_by_min_score(
    memories: Sequence[Memory],
    min_score: float,
) -> tuple[Memory, ...]:
    if min_score <= 0:
        return tuple(memories)
    return tuple(m for m in memories if m.score >= min_score)


def search(
    user_id: str,
    query: str,
    *,
    config: Mem0ClientConfig | None = None,
    post_json: PostJsonFn | None = None,
    min_score: float | None = None,
) -> tuple[Memory, ...]:
    """
    Busca memórias episódicas no mem0 (fail-open → tuple vazio).

    Toda chamada inclui user_id validado (isolamento jean/tati).
    """
    if not user_id or not query.strip():
        return ()

    cfg = config if config is not None else load_config()
    poster = post_json if post_json is not None else _post_json
    url = f"{cfg.api_url}/search"
    payload: dict[str, Any] = {
        "query": query.strip(),
        "user_id": user_id,
        "limit": cfg.search_limit,
    }

    data = poster(url, payload, cfg.timeout)
    if not data:
        return ()
    threshold = min_score if min_score is not None else cfg.min_score
    parsed = _parse_search_results(data)
    filtered = _filter_by_min_score(parsed, threshold)
    return filtered


def add(
    user_id: str,
    messages: Sequence[ChatMessage],
    *,
    config: Mem0ClientConfig | None = None,
    post_json: PostJsonFn | None = None,
) -> None:
    """Persiste troca no mem0 com extração LLM (infer=true, fail-open)."""
    if not user_id or not messages:
        return

    cfg = config if config is not None else load_config()
    poster = post_json if post_json is not None else _post_json
    url = f"{cfg.api_url}/memories"
    payload = {
        "user_id": user_id,
        "messages": [_message_to_api(m) for m in messages],
    }

    data = poster(url, payload, cfg.add_timeout)
    if data is None:
        logger.error("mem0 add failed user_id=%s (timeout=%ss)", user_id, cfg.add_timeout)
    else:
        logger.info("mem0 add ok user_id=%s infer=True", user_id)


def add_direct(
    user_id: str,
    memory_text: str,
    *,
    config: Mem0ClientConfig | None = None,
    post_json: PostJsonFn | None = None,
) -> None:
    """Grava fato literal no mem0 sem extração LLM (infer=false, fail-open)."""
    text = memory_text.strip()
    if not user_id or not text:
        return

    cfg = config if config is not None else load_config()
    poster = post_json if post_json is not None else _post_json
    url = f"{cfg.api_url}/memories"
    payload: dict[str, Any] = {
        "user_id": user_id,
        "messages": [{"role": "user", "content": text}],
        "infer": False,
    }

    data = poster(url, payload, cfg.add_timeout)
    if data is None:
        logger.error("mem0 add_direct failed user_id=%s text=%r (timeout=%ss)", user_id, text, cfg.add_timeout)
    else:
        logger.info("mem0 add_direct ok user_id=%s text=%r", user_id, text)


def add_async(
    user_id: str,
    messages: Sequence[ChatMessage],
    *,
    config: Mem0ClientConfig | None = None,
    post_json: PostJsonFn | None = None,
) -> None:
    """Dispara add em thread daemon — não bloqueia resposta ao usuário."""
    if not user_id or not messages:
        logger.info("mem0 add_async skipped user_id=%r n_msgs=%d", user_id, len(messages) if messages else 0)
        return

    cfg = config if config is not None else load_config()
    poster = post_json if post_json is not None else _post_json
    msgs = tuple(messages)
    logger.info("mem0 add_async dispatch user_id=%s n_msgs=%d", user_id, len(msgs))

    def _worker() -> None:
        add(user_id, msgs, config=cfg, post_json=poster)

    thread = threading.Thread(target=_worker, name=f"mem0-add-{user_id}", daemon=True)
    thread.start()


def add_direct_async(
    user_id: str,
    memory_text: str,
    *,
    config: Mem0ClientConfig | None = None,
    post_json: PostJsonFn | None = None,
) -> None:
    """Dispara add_direct em thread daemon."""
    if not user_id or not memory_text.strip():
        logger.info("mem0 add_direct_async skipped user_id=%r text=%r", user_id, memory_text)
        return

    cfg = config if config is not None else load_config()
    poster = post_json if post_json is not None else _post_json
    text = memory_text.strip()
    logger.info("mem0 add_direct_async dispatch user_id=%s text=%r", user_id, text)

    def _worker() -> None:
        add_direct(user_id, text, config=cfg, post_json=poster)

    thread = threading.Thread(
        target=_worker, name=f"mem0-add-direct-{user_id}", daemon=True
    )
    thread.start()
