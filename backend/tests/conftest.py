"""Fixtures compartidas de la suite de tests."""

import asyncio
import os
from collections.abc import AsyncIterator

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_TEST_URL",
    "postgresql+asyncpg://smartdocs:smartdocs@localhost:5432/smartdocs_test",
)

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET"] = "test-secret-with-at-least-32-characters-long"
os.environ["PASSWORD_MIN_LENGTH"] = "12"

import app.models  # noqa: F401  (registra los modelos en el metadata)
import pytest
import pytest_asyncio
from app.api.dependencies import get_db
from app.core.config import get_settings
from app.core.security import hash_password
from app.database.base import Base
from app.main import create_app
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

get_settings.cache_clear()

DEFAULT_PASSWORD = "Correct-Horse-Battery-9"


async def _reset_schema() -> None:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def database_schema() -> AsyncIterator[None]:
    asyncio.run(_reset_schema())
    yield
    asyncio.run(_reset_schema())


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    application = create_app()

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


async def create_organization(
    session: AsyncSession, *, name: str = "Acme", slug: str = "acme"
) -> Organization:
    return await OrganizationRepository(session).create(name=name, slug=slug)


async def create_user(
    session: AsyncSession,
    organization: Organization,
    *,
    email: str = "admin@acme.com",
    name: str = "Admin Acme",
    password: str = DEFAULT_PASSWORD,
    role: UserRole = UserRole.ADMIN,
    is_active: bool = True,
) -> User:
    return await UserRepository(session).create(
        organization_id=organization.id,
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )


@pytest_asyncio.fixture
async def org_a(db_session: AsyncSession) -> Organization:
    return await create_organization(db_session, name="Acme", slug="acme")


@pytest_asyncio.fixture
async def org_b(db_session: AsyncSession) -> Organization:
    return await create_organization(db_session, name="Globex", slug="globex")


@pytest_asyncio.fixture
async def admin_a(db_session: AsyncSession, org_a: Organization) -> User:
    return await create_user(db_session, org_a)


@pytest_asyncio.fixture
async def user_a(db_session: AsyncSession, org_a: Organization) -> User:
    return await create_user(
        db_session,
        org_a,
        email="user@acme.com",
        name="User Acme",
        role=UserRole.USER,
    )


@pytest_asyncio.fixture
async def admin_b(db_session: AsyncSession, org_b: Organization) -> User:
    return await create_user(
        db_session,
        org_b,
        email="admin@globex.com",
        name="Admin Globex",
    )
