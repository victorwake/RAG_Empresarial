"""Casos de uso de autenticación."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    TokenPair,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    password_needs_rehash,
    refresh_token_matches,
    verify_password,
)
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository

INVALID_CREDENTIALS = "Credenciales inválidas."


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._organizations = OrganizationRepository(session)
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)

    async def login(self, *, organization_slug: str, email: str, password: str) -> TokenPair:
        organization = await self._organizations.get_by_slug(organization_slug)
        if organization is None:
            raise UnauthorizedError(INVALID_CREDENTIALS)

        user = await self._users.get_by_org_and_email(organization.id, email)
        if user is None or not user.is_active:
            raise UnauthorizedError(INVALID_CREDENTIALS)

        if not verify_password(password, user.password_hash):
            raise UnauthorizedError(INVALID_CREDENTIALS)

        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        pair = await self._issue_tokens(user)
        await self._session.commit()
        return pair

    async def refresh(self, refresh_token: str) -> TokenPair:
        payload = decode_token(refresh_token, settings=self._settings, expected_type="refresh")
        record = await self._get_record(payload)
        if record is None:
            raise UnauthorizedError("Token inválido.")

        if record.revoked_at is not None:
            await self._invalidate_session(record.user_id)
            raise UnauthorizedError("Token revocado.")

        if record.expires_at <= datetime.now(UTC):
            raise UnauthorizedError("El token expiró.")

        if not refresh_token_matches(record.token_hash, refresh_token):
            raise UnauthorizedError("Token inválido.")

        user = await self._users.get_by_id(record.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError(INVALID_CREDENTIALS)
        if payload.get("ver") != user.token_version:
            raise UnauthorizedError("Sesión inválida.")

        record.revoked_at = datetime.now(UTC)
        pair = await self._issue_tokens(user)
        await self._session.commit()
        return pair

    async def logout(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token, settings=self._settings, expected_type="refresh")
        except UnauthorizedError:
            return

        record = await self._get_record(payload)
        if record is None or record.revoked_at is not None:
            return

        record.revoked_at = datetime.now(UTC)
        await self._session.commit()

    async def _issue_tokens(self, user: User) -> TokenPair:
        role = user.role.value if hasattr(user.role, "value") else str(user.role)
        access_token = create_access_token(
            user_id=user.id,
            organization_id=user.organization_id,
            role=role,
            token_version=user.token_version,
            settings=self._settings,
        )
        refresh_token, token_hash, jti, expires_at = create_refresh_token(
            user_id=user.id,
            organization_id=user.organization_id,
            role=role,
            token_version=user.token_version,
            settings=self._settings,
        )
        await self._refresh_tokens.create(
            user_id=user.id,
            jti=jti,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._settings.access_token_expire_minutes * 60,
        )

    async def _get_record(self, payload: dict):
        try:
            jti = uuid.UUID(str(payload.get("jti")))
        except (ValueError, TypeError) as exc:
            raise UnauthorizedError("Token inválido.") from exc
        return await self._refresh_tokens.get_by_jti(jti)

    async def _invalidate_session(self, user_id: uuid.UUID) -> None:
        await self._refresh_tokens.revoke_all_for_user(user_id)
        user = await self._users.get_by_id(user_id)
        if user is not None:
            user.token_version += 1
        await self._session.commit()
