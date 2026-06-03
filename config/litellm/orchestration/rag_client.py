"""Cliente HTTP AnythingLLM — vector-search com timeout fail-open (orquestração pura)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from orchestration.types import RagChunk

logger = logging.getLogger(__name__)

DEFAULT_ANYTHINGLLM_API_URL = "http://anythingllm:3001"
DEFAULT_RAG_TIMEOUT = 2.0
DEFAULT_TOP_N = 8
DEFAULT_SCORE_THRESHOLD = 0.25

# Espelha config/anythingllm/workspaces.yaml (litellm monta só config/litellm no container).
DEFAULT_WORKSPACE_SLUGS: dict[str, str] = {
    "jean": "jean-carlos-de-souza",
    "tati": "tatiane-schluter-de-souza",
}

PostJsonFn = Callable[[str, dict[str, Any], float, dict[str, str]], dict[str, Any] | None]


@dataclass(frozen=True)
class RagClientConfig:
    api_url: str
    api_key: str
    timeout: float
    top_n: int
    score_threshold: float
    workspace_slugs: Mapping[str, str]


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _load_workspace_slugs(environ: Mapping[str, str]) -> dict[str, str]:
    raw = environ.get("RAG_WORKSPACE_SLUGS", "").strip()
    if not raw:
        return dict(DEFAULT_WORKSPACE_SLUGS)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except json.JSONDecodeError:
        logger.warning("RAG_WORKSPACE_SLUGS inválido — usando defaults")
    return dict(DEFAULT_WORKSPACE_SLUGS)


def load_config(environ: Mapping[str, str] | None = None) -> RagClientConfig:
    env = environ if environ is not None else os.environ
    api_url = env.get("ANYTHINGLLM_API_URL", DEFAULT_ANYTHINGLLM_API_URL).strip()
    api_url = api_url or DEFAULT_ANYTHINGLLM_API_URL
    api_key = env.get("ANYTHINGLLM_API_KEY", "").strip()
    return RagClientConfig(
        api_url=api_url.rstrip("/"),
        api_key=api_key,
        timeout=_env_float("RAG_TIMEOUT", DEFAULT_RAG_TIMEOUT),
        top_n=_env_int("RAG_TOP_N", DEFAULT_TOP_N),
        score_threshold=_env_float("RAG_SCORE_THRESHOLD", DEFAULT_SCORE_THRESHOLD),
        workspace_slugs=_load_workspace_slugs(env),
    )


def workspace_slug_for_user(user_id: str, *, config: RagClientConfig | None = None) -> str | None:
    """Slug AnythingLLM para user_id (jean|tati)."""
    cfg = config if config is not None else load_config()
    return cfg.workspace_slugs.get(user_id)


def _post_json(
    url: str,
    payload: dict[str, Any],
    timeout: float,
    headers: dict[str, str],
) -> dict[str, Any] | None:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={**headers, "Content-Type": "application/json", "Accept": "application/json"},
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
        logger.warning("AnythingLLM request failed url=%s error=%s", url, exc)
        return None


def _chunk_source(metadata: Mapping[str, Any]) -> str:
    for key in ("title", "chunkSource", "url", "docSource"):
        value = metadata.get(key)
        if value:
            return str(value)
    return "documento"


def _parse_vector_results(data: dict[str, Any]) -> tuple[RagChunk, ...]:
    raw_results = data.get("results")
    if not isinstance(raw_results, list):
        return ()

    chunks: list[RagChunk] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not text:
            continue
        meta_raw = item.get("metadata")
        metadata: dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
        source = _chunk_source(metadata)
        score_raw = item.get("score")
        if score_raw is None:
            distance = item.get("distance")
            try:
                score = 1.0 - float(distance) if distance is not None else 0.0
            except (TypeError, ValueError):
                score = 0.0
        else:
            try:
                score = float(score_raw)
            except (TypeError, ValueError):
                score = 0.0
        chunks.append(
            RagChunk(text=str(text).strip(), source=source, score=score, metadata=metadata)
        )
    return tuple(chunks)


def retrieve(
    user_id: str,
    query: str,
    *,
    config: RagClientConfig | None = None,
    post_json: PostJsonFn | None = None,
) -> tuple[RagChunk, ...]:
    """
    Busca chunks no workspace AnythingLLM do usuário (fail-open → tuple vazio).

    Requer ANYTHINGLLM_API_KEY e slug mapeado para user_id.
    """
    if not user_id or not query.strip():
        return ()

    cfg = config if config is not None else load_config()
    if not cfg.api_key:
        logger.debug("rag_client: ANYTHINGLLM_API_KEY ausente — skip retrieval")
        return ()

    slug = workspace_slug_for_user(user_id, config=cfg)
    if not slug:
        logger.warning("rag_client: sem workspace para user_id=%s", user_id)
        return ()

    poster = post_json if post_json is not None else _post_json
    url = f"{cfg.api_url}/api/v1/workspace/{slug}/vector-search"
    payload: dict[str, Any] = {
        "query": query.strip(),
        "topN": cfg.top_n,
        "scoreThreshold": cfg.score_threshold,
    }
    headers = {"Authorization": f"Bearer {cfg.api_key}"}

    data = poster(url, payload, cfg.timeout, headers)
    if not data:
        return ()
    return _parse_vector_results(data)
