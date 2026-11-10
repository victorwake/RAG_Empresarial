"""Pruebas de integración del servicio de procesamiento."""

import uuid
from contextlib import asynccontextmanager

import pytest
from app.interfaces.storage import LocalFileStorage
from app.models.document import Document
from app.models.enums import DocumentStatus, JobStatus, JobType
from app.models.organization import Organization
from app.models.processing_job import ProcessingJob
from app.repositories.processing_job_repository import ProcessingJobRepository
from app.services import processing_service
from app.services.processing_service import (
    DOCUMENT_DELETED_MESSAGE,
    FILE_UNAVAILABLE_MESSAGE,
    ProcessingService,
    reconcile_orphan_jobs,
    run_processing_job,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import create_document, create_processing_job

EMPTY_FILE_MESSAGE = "El archivo del documento está vacío o truncado."
INTERRUPTED_MESSAGE = "Interrumpido por reinicio del proceso"


async def _create_document_with_file(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a, *, content: bytes
) -> Document:
    storage = LocalFileStorage(tmp_path)
    storage_path = await storage.save(org_a.id, content, "informe.pdf")
    return await create_document(
        db_session, org_a, admin_a, storage_path=storage_path, content=content
    )


async def test_run_job_completes_document(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await _create_document_with_file(
        db_session, tmp_path, org_a, admin_a, content=b"%PDF-1.7 contenido"
    )
    job = await create_processing_job(db_session, document)
    service = ProcessingService(db_session, LocalFileStorage(tmp_path))

    await service.run_job(document_id=document.id, job_id=job.id)

    assert document.status == DocumentStatus.COMPLETED
    assert job.status == JobStatus.COMPLETED
    assert job.attempts == 1
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.error_message is None


async def test_run_job_is_idempotent_for_completed_job(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await _create_document_with_file(
        db_session, tmp_path, org_a, admin_a, content=b"%PDF-1.7 contenido"
    )
    job = await create_processing_job(db_session, document)
    service = ProcessingService(db_session, LocalFileStorage(tmp_path))

    await service.run_job(document_id=document.id, job_id=job.id)
    await service.run_job(document_id=document.id, job_id=job.id)

    assert job.status == JobStatus.COMPLETED
    assert job.attempts == 1


async def test_run_job_ignores_unknown_job(
    db_session: AsyncSession, tmp_path
) -> None:
    service = ProcessingService(db_session, LocalFileStorage(tmp_path))

    await service.run_job(document_id=uuid.uuid4(), job_id=uuid.uuid4())


async def test_run_job_fails_when_document_is_missing(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await create_document(db_session, org_a, admin_a)
    job = await create_processing_job(db_session, document)
    service = ProcessingService(db_session, LocalFileStorage(tmp_path))

    await service.run_job(document_id=uuid.uuid4(), job_id=job.id)

    assert job.status == JobStatus.FAILED
    assert job.error_message == DOCUMENT_DELETED_MESSAGE


async def test_run_job_fails_when_file_is_missing(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await create_document(
        db_session, org_a, admin_a, storage_path=f"{org_a.id}/{uuid.uuid4()}.pdf"
    )
    job = await create_processing_job(db_session, document)
    service = ProcessingService(db_session, LocalFileStorage(tmp_path))

    await service.run_job(document_id=document.id, job_id=job.id)

    assert job.status == JobStatus.FAILED
    assert job.error_message == FILE_UNAVAILABLE_MESSAGE
    assert document.status == DocumentStatus.FAILED


async def test_run_job_fails_when_file_is_empty(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    storage = LocalFileStorage(tmp_path)
    storage_path = await storage.save(org_a.id, b"", "vacio.pdf")
    document = await create_document(
        db_session,
        org_a,
        admin_a,
        storage_path=storage_path,
        content=b"%PDF-1.7 contenido",
    )
    job = await create_processing_job(db_session, document)
    service = ProcessingService(db_session, storage)

    await service.run_job(document_id=document.id, job_id=job.id)

    assert job.status == JobStatus.FAILED
    assert job.error_message == EMPTY_FILE_MESSAGE
    assert document.status == DocumentStatus.FAILED


async def test_claim_is_atomic(
    db_session: AsyncSession, org_a: Organization, admin_a
) -> None:
    document = await create_document(db_session, org_a, admin_a)
    job = await create_processing_job(db_session, document)
    repository = ProcessingJobRepository(db_session)

    assert await repository.claim(job.id) is True
    assert await repository.claim(job.id) is False


async def test_second_active_job_is_rejected_by_partial_index(
    db_session: AsyncSession, org_a: Organization, admin_a
) -> None:
    document = await create_document(db_session, org_a, admin_a)
    await create_processing_job(db_session, document)

    db_session.add(
        ProcessingJob(
            document_id=document.id,
            organization_id=document.organization_id,
            job_type=JobType.REPROCESS,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    repository = ProcessingJobRepository(db_session)
    assert await repository.get_active_for_document(document.id) is None


async def test_reconcile_orphan_jobs_marks_stale_as_failed(
    db_session: AsyncSession, org_a: Organization, admin_a, monkeypatch
) -> None:
    stale_document = await create_document(db_session, org_a, admin_a, filename="huerfano.pdf")
    stale_job = await create_processing_job(db_session, stale_document, status=JobStatus.PROCESSING)
    finished_document = await create_document(db_session, org_a, admin_a, filename="listo.pdf")
    finished_document.status = DocumentStatus.COMPLETED
    finished_job = await create_processing_job(
        db_session, finished_document, status=JobStatus.COMPLETED
    )
    await db_session.flush()

    @asynccontextmanager
    async def _fake_session_scope():
        yield db_session

    monkeypatch.setattr(processing_service, "session_scope", _fake_session_scope)
    jobs, documents = await reconcile_orphan_jobs()

    assert jobs == 1
    assert documents == 1
    stale_job_id = stale_job.id
    stale_document_id = stale_document.id
    finished_job_id = finished_job.id
    db_session.expire_all()
    stale_job_after = await db_session.get(ProcessingJob, stale_job_id)
    stale_document_after = await db_session.get(Document, stale_document_id)
    finished_job_after = await db_session.get(ProcessingJob, finished_job_id)
    assert stale_job_after.status == JobStatus.FAILED
    assert stale_job_after.error_message == INTERRUPTED_MESSAGE
    assert stale_document_after.status == DocumentStatus.FAILED
    assert finished_job_after.status == JobStatus.COMPLETED


async def test_run_processing_job_entry_point_completes_document(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a, monkeypatch
) -> None:
    storage = LocalFileStorage(tmp_path)
    content = b"%PDF-1.7 contenido"
    storage_path = await storage.save(org_a.id, content, "informe.pdf")
    document = await create_document(
        db_session, org_a, admin_a, storage_path=storage_path, content=content
    )
    job = await create_processing_job(db_session, document)

    @asynccontextmanager
    async def _fake_session_scope():
        yield db_session

    monkeypatch.setattr(processing_service, "session_scope", _fake_session_scope)
    monkeypatch.setattr(processing_service, "LocalFileStorage", lambda root: storage)
    await run_processing_job(document.id, job.id)

    document_id = document.id
    job_id = job.id
    db_session.expire_all()
    document_after = await db_session.get(Document, document_id)
    job_after = await db_session.get(ProcessingJob, job_id)
    assert document_after.status == DocumentStatus.COMPLETED
    assert job_after.status == JobStatus.COMPLETED
