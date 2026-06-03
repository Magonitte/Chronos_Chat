"""Testes de validação X-User-Id (fail-closed)."""

import pytest

from orchestration.user_id import (
    ALLOWED_USER_IDS,
    InvalidUserIdError,
    allowed_user_ids_from_env,
    extract_user_id,
)


@pytest.mark.parametrize("user_id", ["jean", "tati"])
def test_extract_user_id_accepts_allowlist(user_id: str) -> None:
    assert extract_user_id({"X-User-Id": user_id}) == user_id


def test_extract_user_id_case_insensitive_header() -> None:
    assert extract_user_id({"x-user-id": "jean"}) == "jean"
    assert extract_user_id({"X-USER-ID": "tati"}) == "tati"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-User-Id": ""},
        {"X-User-Id": "   "},
        {"X-User-Id": "admin"},
        {"X-User-Id": "Jean"},
        {"Authorization": "Bearer x"},
    ],
)
def test_extract_user_id_rejects_invalid_or_missing(headers: dict[str, str]) -> None:
    with pytest.raises(InvalidUserIdError):
        extract_user_id(headers)


def test_invalid_user_id_error_message_absent() -> None:
    err = InvalidUserIdError(None)
    assert "ausente" in str(err)
    assert err.received is None


def test_invalid_user_id_error_message_invalid() -> None:
    err = InvalidUserIdError("admin")
    assert "admin" in str(err)
    assert err.received == "admin"


def test_allowed_user_ids_from_env_override() -> None:
    custom = allowed_user_ids_from_env({"ALLOWED_USER_IDS": "jean,tati"})
    assert custom == ALLOWED_USER_IDS


def test_extract_user_id_explicit_allowlist() -> None:
    assert extract_user_id({"X-User-Id": "jean"}, allowed=frozenset({"jean"})) == "jean"
    with pytest.raises(InvalidUserIdError):
        extract_user_id({"X-User-Id": "tati"}, allowed=frozenset({"jean"}))
