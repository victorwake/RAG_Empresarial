"""Contexto de request y de tenant propagado por las capas de la aplicación."""

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from app.models.enums import UserRole

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)
_organization_id: ContextVar[str | None] = ContextVar("organization_id", default=None)


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Identidad autenticada. La organización nunca proviene del cliente."""

    user_id: UUID
    organization_id: UUID
    role: UserRole


def set_request_id(value: str | None) -> None:
    _request_id.set(value)


def get_request_id() -> str | None:
    return _request_id.get()


def set_identity_context(user_id: str | None, organization_id: str | None) -> None:
    _user_id.set(user_id)
    _organization_id.set(organization_id)


def get_user_id() -> str | None:
    return _user_id.get()


def get_organization_id() -> str | None:
    return _organization_id.get()


def clear_context() -> None:
    _request_id.set(None)
    _user_id.set(None)
    _organization_id.set(None)
