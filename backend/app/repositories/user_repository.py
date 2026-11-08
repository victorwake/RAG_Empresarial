"""Repositorio de usuarios. Toda consulta incluye la organización del token."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_org_and_email(self, organization_id: uuid.UUID, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(
                User.organization_id == organization_id,
                User.email == email,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        name: str,
        email: str,
        password_hash: str,
        role: UserRole = UserRole.USER,
        is_active: bool = True,
    ) -> User:
        user = User(
            organization_id=organization_id,
            name=name,
            email=email,
            password_hash=password_hash,
            role=role,
            is_active=is_active,
        )
        self._session.add(user)
        await self._session.flush()
        return user
