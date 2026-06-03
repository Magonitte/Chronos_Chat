"""Mensagem clara quando llama-server (host :8080) está offline — T8.2."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

# Mensagem exibida no LibreChat (OpenAI-compatible error.message).
LLAMA_OFFLINE_USER_MESSAGE = (
    "O servidor de inferência local (llama-server) não está disponível. "
    "No Windows, execute scripts\\Server_Qwen3.6-35B.bat e aguarde o modelo carregar. "
    "Confira com: curl http://127.0.0.1:8080/v1/models"
)

LLAMA_OFFLINE_ERROR_TYPE = "llama_server_offline"
LLAMA_OFFLINE_ERROR_CODE = "llama_server_offline"

_CONNECTION_MARKERS = (
    "apiconnectionerror",
    "connection error",
    "connection refused",
    "connect call failed",
    "failed to establish",
    "all connection attempts failed",
    "name or service not known",
    "nodename nor servname",
    "host.docker.internal",
    ":8080",
    "llama",
    "unreachable",
    "timed out connecting",
    "connection reset",
)


def is_llama_unreachable(exc: BaseException) -> bool:
    """
    True se a falha indica que o backend llama.cpp (:8080) não respondeu.
    """
    if isinstance(exc, (ConnectionError, OSError)):
        return True

    type_name = type(exc).__name__.lower()
    if "connection" in type_name or type_name in ("connecttimeout", "readtimeout"):
        return True

    module = getattr(type(exc), "__module__", "") or ""
    if "litellm" in module and "connection" in type_name:
        return True

    try:
        from litellm.exceptions import APIConnectionError

        if isinstance(exc, APIConnectionError):
            return True
    except ImportError:
        pass

    try:
        import httpx

        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
            return True
    except ImportError:
        pass

    text = _exception_text(exc).lower()
    if not text:
        return False
    return any(marker in text for marker in _CONNECTION_MARKERS)


def _exception_text(exc: BaseException) -> str:
    parts: list[str] = [str(exc)]
    cause = exc.__cause__
    if cause is not None:
        parts.append(str(cause))
    ctx = exc.__context__
    if ctx is not None and ctx is not cause:
        parts.append(str(ctx))
    return " ".join(parts)


def build_llama_offline_http_exception(
    *,
    request_id: str | None = None,
) -> HTTPException:
    """HTTP 503 com corpo OpenAI-compatible para o cliente (LibreChat)."""
    message = LLAMA_OFFLINE_USER_MESSAGE
    if request_id:
        message = f"{message} (request_id: {request_id})"

    detail: dict[str, Any] = {
        "error": {
            "message": message,
            "type": LLAMA_OFFLINE_ERROR_TYPE,
            "code": LLAMA_OFFLINE_ERROR_CODE,
        }
    }
    return HTTPException(status_code=503, detail=detail)


def llama_offline_from_failure(
    original_exception: Exception,
    request_data: dict[str, Any] | None = None,
) -> HTTPException | None:
    """
    Retorna HTTPException amigável se a falha for llama offline; senão None.
    """
    if not is_llama_unreachable(original_exception):
        return None

    request_id: str | None = None
    if isinstance(request_data, dict):
        from hooks.observability import request_id_from_metadata

        meta = request_data.get("metadata")
        if isinstance(meta, dict):
            request_id = request_id_from_metadata(meta)
        if not request_id:
            rid = request_data.get("litellm_call_id")
            if isinstance(rid, str) and rid.strip():
                request_id = rid.strip()

    return build_llama_offline_http_exception(request_id=request_id)
