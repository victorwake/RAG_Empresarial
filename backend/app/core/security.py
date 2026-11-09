"""Utilidades de seguridad: hashes Argon2id y tokens JWT/refresh."""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"  # noqa: S105


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _encode(payload: dict, settings: Settings) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role: str,
    token_version: int,
    settings: Settings,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": role,
        "ver": token_version,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    return _encode(payload, settings)


def create_refresh_token(
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role: str,
    token_version: int,
    settings: Settings,
) -> tuple[str, str, uuid.UUID, datetime]:
    """Devuelve (token, hash, jti, expiración). El token en claro no se persiste."""
    now = datetime.now(UTC)
    jti = uuid.uuid4()
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": role,
        "ver": token_version,
        "jti": str(jti),
        "iat": now,
        "exp": expires_at,
        "type": "refresh",
    }
    token = _encode(payload, settings)
    return token, hash_refresh_token(token), jti, expires_at


def decode_token(token: str, *, settings: Settings, expected_type: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("El token expiró.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Token inválido.") from exc

    if payload.get("type") != expected_type:
        raise UnauthorizedError("Token inválido.")
    return payload


def refresh_token_matches(stored_hash: str, token: str) -> bool:
    return hmac.compare_digest(stored_hash, hash_refresh_token(token))


def generate_jti() -> uuid.UUID:
    return uuid.uuid4()


def generate_secret() -> str:
    return secrets.token_urlsafe(48)
