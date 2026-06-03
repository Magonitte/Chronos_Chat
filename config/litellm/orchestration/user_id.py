"""Validação fail-closed do header X-User-Id (jean | tati)."""

from __future__ import annotations

import os
from typing import Mapping

ALLOWED_USER_IDS: frozenset[str] = frozenset({"jean", "tati"})

HEADER_NAME = "x-user-id"


class InvalidUserIdError(ValueError):
    """Header X-User-Id ausente ou fora da allowlist."""

    def __init__(self, received: str | None) -> None:
        self.received = received
        if received is None:
            msg = "X-User-Id ausente"
        else:
            msg = f"X-User-Id inválido: {received!r}"
        super().__init__(msg)


def allowed_user_ids_from_env(
    environ: Mapping[str, str] | None = None,
) -> frozenset[str]:
    """Allowlist opcional via ALLOWED_USER_IDS (jean,tati). Padrão: jean|tati."""
    env = environ if environ is not None else os.environ
    raw = env.get("ALLOWED_USER_IDS", "").strip()
    if not raw:
        return ALLOWED_USER_IDS
    ids = frozenset(uid.strip() for uid in raw.split(",") if uid.strip())
    return ids if ids else ALLOWED_USER_IDS


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            stripped = value.strip() if isinstance(value, str) else str(value).strip()
            return stripped if stripped else None
    return None


def extract_user_id(
    headers: Mapping[str, str],
    *,
    allowed: frozenset[str] | None = None,
) -> str:
    """
    Extrai e valida X-User-Id. Fail-closed: sem fallback.

    Raises:
        InvalidUserIdError: header ausente, vazio ou fora da allowlist.
    """
    allowlist = allowed if allowed is not None else allowed_user_ids_from_env()
    user_id = _get_header(headers, HEADER_NAME)
    if not user_id or user_id not in allowlist:
        raise InvalidUserIdError(user_id)
    return user_id
