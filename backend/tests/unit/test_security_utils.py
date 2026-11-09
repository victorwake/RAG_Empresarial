"""Pruebas unitarias de utilidades de seguridad."""

import uuid

import pytest
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    password_needs_rehash,
    refresh_token_matches,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    password = "Correct-Horse-Battery-9"
    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2id$")
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)
    assert not verify_password(password, "not-a-hash")


def test_password_needs_rehash_for_invalid_hash() -> None:
    assert password_needs_rehash("not-a-hash")
    assert not password_needs_rehash(hash_password("Correct-Horse-Battery-9"))


def test_access_token_roundtrip() -> None:
    settings = get_settings()
    user_id = uuid.uuid4()
    organization_id = uuid.uuid4()

    token = create_access_token(
        user_id=user_id,
        organization_id=organization_id,
        role="ADMIN",
        token_version=3,
        settings=settings,
    )
    payload = decode_token(token, settings=settings, expected_type="access")

    assert payload["sub"] == str(user_id)
    assert payload["org"] == str(organization_id)
    assert payload["role"] == "ADMIN"
    assert payload["ver"] == 3


def test_token_type_is_enforced() -> None:
    settings = get_settings()
    token = create_access_token(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        role="USER",
        token_version=0,
        settings=settings,
    )

    with pytest.raises(UnauthorizedError):
        decode_token(token, settings=settings, expected_type="refresh")


def test_refresh_token_is_hashed_and_comparable() -> None:
    settings = get_settings()
    token, token_hash, jti, expires_at = create_refresh_token(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        role="USER",
        token_version=0,
        settings=settings,
    )

    assert token_hash == hash_refresh_token(token)
    assert len(token_hash) == 64
    assert refresh_token_matches(token_hash, token)
    assert not refresh_token_matches(token_hash, f"{token}x")
    assert jti
    assert expires_at.tzinfo is not None


def test_invalid_token_raises_unauthorized() -> None:
    settings = get_settings()
    with pytest.raises(UnauthorizedError):
        decode_token("not-a-jwt", settings=settings, expected_type="access")
