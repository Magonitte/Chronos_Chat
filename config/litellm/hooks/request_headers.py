"""Extrai headers HTTP do payload LiteLLM (proxy_server_request / metadata)."""

from __future__ import annotations

from typing import Any


def extract_request_headers(data: dict[str, Any]) -> dict[str, str]:
    """
    Headers da requisição original ao proxy.

    LiteLLM popula ``proxy_server_request.headers`` e ``metadata.headers``.
    """
    headers: dict[str, str] = {}

    proxy_req = data.get("proxy_server_request")
    if isinstance(proxy_req, dict):
        raw = proxy_req.get("headers")
        if isinstance(raw, dict):
            headers = {str(k): str(v) for k, v in raw.items()}

    if not headers:
        meta = data.get("metadata")
        if isinstance(meta, dict):
            raw = meta.get("headers")
            if isinstance(raw, dict):
                headers = {str(k): str(v) for k, v in raw.items()}

    return headers
