"""Fixtures compartidas de la suite de tests."""

import asyncio
import hashlib
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

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
from app.api.dependencies import get_db, get_file_storage, get_processing_queue
from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password
from app.database.base import Base
from app.interfaces.queue import ProcessingQueue
from app.interfaces.storage import FileStorage, LocalFileStorage
from app.main import create_app
from app.models.document import Document
from app.models.enums import JobStatus, JobType, UserRole
from app.models.organization import Organization
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.processing_job_repository import ProcessingJobRepository
from app.repositories.user_repository import UserRepository
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

get_settings.cache_clear()

DEFAULT_PASSWORD = "Correct-Horse-Battery-9"

PDF_BYTES = b"%PDF-1.7 contenido simulado de un archivo pdf"
DOCX_BYTES = b"PK\x03\x04 contenido simulado de un archivo docx"
TXT_BYTES = b"Contenido de texto plano simulado."


class FakeProcessingQueue:
    """Cola falsa: registra los encolados sin ejecutar trabajos."""

    def __init__(self) -> None:
        self.ingestions: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.reprocesses: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def enqueue_ingestion(self, document_id: uuid.UUID, job_id: uuid.UUID) -> None:
        self.ingestions.append((document_id, job_id))

    async def enqueue_reprocess(self, document_id: uuid.UUID, job_id: uuid.UUID) -> None:
        self.reprocesses.append((document_id, job_id))


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


def _build_application(
    db_session: AsyncSession,
    *,
    storage: FileStorage,
    queue: ProcessingQueue,
    settings: Settings | None = None,
) -> FastAPI:
    application = create_app()

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db] = _override_get_db
    application.dependency_overrides[get_file_storage] = lambda: storage
    application.dependency_overrides[get_processing_queue] = lambda: queue
    if settings is not None:
        application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest_asyncio.fixture
async def fake_queue() -> AsyncIterator[FakeProcessingQueue]:
    yield FakeProcessingQueue()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, tmp_path: Path, fake_queue: FakeProcessingQueue
) -> AsyncIterator[AsyncClient]:
    application = _build_application(
        db_session, storage=LocalFileStorage(tmp_path), queue=fake_queue
    )
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def strict_client(
    db_session: AsyncSession, tmp_path: Path, fake_queue: FakeProcessingQueue
) -> AsyncIterator[AsyncClient]:
    settings = Settings(max_upload_mb=1)
    application = _build_application(
        db_session,
        storage=LocalFileStorage(tmp_path / "strict"),
        queue=fake_queue,
        settings=settings,
    )
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


def auth_headers(user: User) -> dict[str, str]:
    """Cabecera Authorization para el usuario dado."""
    token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role.value,
        token_version=user.token_version,
        settings=get_settings(),
    )
    return {"Authorization": f"Bearer {token}"}


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


async def create_document(
    session: AsyncSession,
    organization: Organization,
    user: User,
    *,
    filename: str = "documento.pdf",
    storage_path: str | None = None,
    content: bytes | None = None,
) -> Document:
    """Crea un documento con checksum único por llamada."""
    payload = content if content is not None else f"contenido-{uuid.uuid4()}".encode()
    return await DocumentRepository(session).create(
        organization_id=organization.id,
        uploaded_by=user.id,
        filename=filename,
        original_filename=filename,
        storage_path=storage_path or f"{organization.id}/{uuid.uuid4()}.pdf",
        mime_type="application/pdf",
        file_size=len(payload),
        checksum=hashlib.sha256(payload).hexdigest(),
    )


async def create_processing_job(
    session: AsyncSession,
    document: Document,
    *,
    job_type: JobType = JobType.INGEST,
    status: JobStatus = JobStatus.PENDING,
) -> ProcessingJob:
    job = await ProcessingJobRepository(session).create(
        document_id=document.id,
        organization_id=document.organization_id,
        job_type=job_type,
    )
    job.status = status
    return job


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
