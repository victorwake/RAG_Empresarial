"""Dependencias de autenticación, tenant, sesión de base de datos y servicios."""

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import BackgroundTasks, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.context import TenantContext, set_identity_context
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.database.session import get_session
from app.interfaces.queue import FastAPIProcessingQueue, ProcessingQueue
from app.interfaces.storage import FileStorage, LocalFileStorage
from app.models.enums import UserRole
from app.models.user import User
from app.rag.embedding_provider import EmbeddingProvider
from app.rag.gemini_embedding import GeminiEmbeddingProvider
from app.repositories.user_repository import UserRepository

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


def get_file_storage(settings: Settings = Depends(get_settings)) -> FileStorage:
    return LocalFileStorage(Path(settings.file_storage_root))


def get_processing_queue(background_tasks: BackgroundTasks) -> ProcessingQueue:
    return FastAPIProcessingQueue(background_tasks)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Token de acceso ausente.")

    payload = decode_token(credentials.credentials, settings=settings, expected_type="access")

    try:
        user_id = uuid.UUID(str(payload["sub"]))
        organization_id = uuid.UUID(str(payload["org"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise UnauthorizedError("Token inválido.") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Sesión inválida.")
    if user.organization_id != organization_id:
        raise UnauthorizedError("Sesión inválida.")
    if payload.get("ver") != user.token_version:
        raise UnauthorizedError("Sesión inválida.")

    set_identity_context(str(user.id), str(user.organization_id))
    return user


def get_tenant_context(user: User = Depends(get_current_user)) -> TenantContext:
    return TenantContext(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
    )


def require_admin(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    if context.role != UserRole.ADMIN:
        raise ForbiddenError("Se requiere rol ADMIN.")
    return context


def get_embedding_provider(
    settings: Settings = Depends(get_settings)
) -> EmbeddingProvider:
    """Proveedor de embeddings — overridable en tests."""
    return GeminiEmbeddingProvider.from_settings(settings)
