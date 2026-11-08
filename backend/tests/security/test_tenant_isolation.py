"""Pruebas de aislamiento por organización y validación de tokens."""

import uuid

import pytest
from app.api.dependencies import require_admin
from app.core.config import get_settings
from app.core.context import TenantContext
from app.core.exceptions import ForbiddenError
from app.core.security import create_access_token, create_refresh_token
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _access_for(
    user: User, *, organization_id: uuid.UUID | None = None, ver: int | None = None
) -> str:
    return create_access_token(
        user_id=user.id,
        organization_id=organization_id or user.organization_id,
        role=user.role.value,
        token_version=user.token_version if ver is None else ver,
        settings=get_settings(),
    )


async def test_token_from_other_organization_is_rejected(
    client: AsyncClient, admin_a: User, org_b: Organization
) -> None:
    forged = _access_for(admin_a, organization_id=org_b.id)

    response = await client.get("/api/v1/auth/me", headers=_headers(forged))

    assert response.status_code == 401


async def test_token_with_wrong_version_is_rejected(client: AsyncClient, admin_a: User) -> None:
    forged = _access_for(admin_a, ver=admin_a.token_version + 1)

    response = await client.get("/api/v1/auth/me", headers=_headers(forged))

    assert response.status_code == 401


async def test_refresh_token_cannot_be_used_as_access(client: AsyncClient, admin_a: User) -> None:
    refresh_token, _, _, _ = create_refresh_token(
        user_id=admin_a.id,
        organization_id=admin_a.organization_id,
        role=admin_a.role.value,
        token_version=admin_a.token_version,
        settings=get_settings(),
    )

    response = await client.get("/api/v1/auth/me", headers=_headers(refresh_token))

    assert response.status_code == 401


async def test_access_token_cannot_be_used_as_refresh(client: AsyncClient, admin_a: User) -> None:
    access = _access_for(admin_a)

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": access})

    assert response.status_code == 401


async def test_deactivated_user_token_is_rejected(
    client: AsyncClient, db_session: AsyncSession, admin_a: User
) -> None:
    token = _access_for(admin_a)
    admin_a.is_active = False
    await db_session.commit()

    response = await client.get("/api/v1/auth/me", headers=_headers(token))

    assert response.status_code == 401


def test_require_admin_rejects_user_role(user_a: User) -> None:
    context = TenantContext(
        user_id=user_a.id,
        organization_id=user_a.organization_id,
        role=UserRole.USER,
    )

    with pytest.raises(ForbiddenError):
        require_admin(context=context)


def test_require_admin_accepts_admin_role(admin_a: User) -> None:
    context = TenantContext(
        user_id=admin_a.id,
        organization_id=admin_a.organization_id,
        role=UserRole.ADMIN,
    )

    assert require_admin(context=context) is context
