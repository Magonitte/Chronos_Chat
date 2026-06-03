"""Logs estruturados JSON para hooks New_Chat (T8.2)."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any, Generator

from hooks.request_headers import extract_request_headers

METADATA_REQUEST_ID_KEY = "newchat_request_id"

_LOGGER = logging.getLogger("newchat.hooks")
_LOGGER.setLevel(logging.INFO)
if not _LOGGER.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _LOGGER.addHandler(_handler)
    _LOGGER.propagate = False


@contextmanager
def timed_call() -> Generator[list[float], None, None]:
    """Mede duração em ms; yield lista de um elemento preenchida no finally."""
    bucket: list[float] = [0.0]
    start = time.perf_counter()
    try:
        yield bucket
    finally:
        bucket[0] = (time.perf_counter() - start) * 1000.0


def resolve_request_id(data: dict[str, Any], headers: dict[str, str] | None = None) -> str:
    """
    request_id estável por request: header X-Request-Id, litellm_call_id ou UUID.
    """
    hdrs = headers if headers is not None else extract_request_headers(data)
    for key in ("X-Request-Id", "x-request-id", "X-Request-ID"):
        raw = hdrs.get(key, "").strip()
        if raw:
            return raw

    litellm_id = data.get("litellm_call_id")
    if isinstance(litellm_id, str) and litellm_id.strip():
        return litellm_id.strip()

    meta = data.get("metadata")
    if isinstance(meta, dict):
        stored = meta.get(METADATA_REQUEST_ID_KEY)
        if isinstance(stored, str) and stored.strip():
            return stored.strip()

    return str(uuid.uuid4())


def ensure_request_id_in_metadata(data: dict[str, Any], request_id: str) -> None:
    meta = data.get("metadata")
    if not isinstance(meta, dict):
        meta = {}
        data["metadata"] = meta
    meta.setdefault(METADATA_REQUEST_ID_KEY, request_id)


def log_event(event: str, **fields: Any) -> None:
    """Uma linha JSON em stderr (parseável por agregadores)."""
    payload: dict[str, Any] = {"event": event, **fields}
    for key, value in list(payload.items()):
        if value is None:
            del payload[key]
    line = json.dumps(payload, ensure_ascii=False, default=str)
    _LOGGER.info(line)


def request_id_from_metadata(meta: dict[str, Any] | None) -> str | None:
    if not isinstance(meta, dict):
        return None
    rid = meta.get(METADATA_REQUEST_ID_KEY)
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    return None
