"""Pruebas de integración del servicio de procesamiento."""

import uuid
from contextlib import asynccontextmanager

import pytest
from app.document_processing import ExtractionResult
from app.document_processing.docx_processor import DOCX_MIME_TYPE
from app.document_processing.pdf_processor import (
    CORRUPT_MESSAGE as PDF_CORRUPT_MESSAGE,
)
from app.document_processing.pdf_processor import (
    NO_TEXT_MESSAGE as PDF_NO_TEXT_MESSAGE,
)
from app.interfaces.storage import LocalFileStorage
from app.models.document import Document
from app.models.enums import DocumentStatus, JobStatus, JobType
from app.models.organization import Organization
from app.models.processing_job import ProcessingJob
from app.repositories.processing_job_repository import ProcessingJobRepository
from app.services import processing_service
from app.services.processing_service import (
    DOCUMENT_DELETED_MESSAGE,
    EMPTY_FILE_MESSAGE,
    FILE_UNAVAILABLE_MESSAGE,
    UNSUPPORTED_TYPE_MESSAGE,
    ProcessingService,
    reconcile_orphan_jobs,
    run_processing_job,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import (
    build_docx_bytes,
    build_pdf_bytes,
    build_scanned_pdf_bytes,
    create_document,
    create_processing_job,
)

INTERRUPTED_MESSAGE = "Interrumpido por reinicio del proceso"


class _ExtractorConAdvertencias:
    """Extractor falso que reporta advertencias sin fallar la extracción."""

    def supports(self, mime_type: str) -> bool:
        return True

    def extract(self, source: bytes) -> ExtractionResult:
        return ExtractionResult(
            text="texto extraido del documento de prueba",
            pages=(),
            page_count=None,
            warnings=("La página 3 no pudo extraerse y fue omitida.",),
        )


async def _create_document_with_file(
    db_session: AsyncSession,
    tmp_path,
    org_a: Organization,
    admin_a,
    *,
    content: bytes,
    filename: str = "informe.pdf",
    mime_type: str = "application/pdf",
) -> Document:
    storage = LocalFileStorage(tmp_path)
    storage_path = await storage.save(org_a.id, content, filename)
    return await create_document(
        db_session,
        org_a,
        admin_a,
        filename=filename,
        storage_path=storage_path,
        content=content,
        mime_type=mime_type,
    )


async def test_run_job_completes_document(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await _create_document_with_file(
        db_session,
        tmp_path,
        org_a,
        admin_a,
        content=build_pdf_bytes(
            "Primera pagina del informe tecnico.", "Segunda pagina del informe tecnico."
        ),
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
    assert document.page_count == 2


async def test_run_job_is_idempotent_for_completed_job(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await _create_document_with_file(
        db_session,
        tmp_path,
        org_a,
        admin_a,
        content=build_pdf_bytes("Informe tecnico de la organizacion."),
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
        content=build_pdf_bytes("Informe tecnico de la organizacion."),
    )
    job = await create_processing_job(db_session, document)
    service = ProcessingService(db_session, storage)

    await service.run_job(document_id=document.id, job_id=job.id)

    assert job.status == JobStatus.FAILED
    assert job.error_message == EMPTY_FILE_MESSAGE
    assert document.status == DocumentStatus.FAILED


async def test_run_job_extracts_docx_document(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await _create_document_with_file(
        db_session,
        tmp_path,
        org_a,
        admin_a,
        content=build_docx_bytes(
            "Parrafo inicial del documento Word.", "Parrafo final del documento Word."
        ),
        filename="memoria.docx",
        mime_type=DOCX_MIME_TYPE,
    )
    job = await create_processing_job(db_session, document)
    service = ProcessingService(db_session, LocalFileStorage(tmp_path))

    await service.run_job(document_id=document.id, job_id=job.id)

    assert document.status == DocumentStatus.COMPLETED
    assert job.status == JobStatus.COMPLETED
    assert job.error_message is None
    assert document.page_count is None


async def test_run_job_extracts_txt_document(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await _create_document_with_file(
        db_session,
        tmp_path,
        org_a,
        admin_a,
        content=b"Notas de la reunion del proyecto SmartDocs.",
        filename="notas.txt",
        mime_type="text/plain",
    )
    job = await create_processing_job(db_session, document)
    service = ProcessingService(db_session, LocalFileStorage(tmp_path))

    await service.run_job(document_id=document.id, job_id=job.id)

    assert document.status == DocumentStatus.COMPLETED
    assert job.status == JobStatus.COMPLETED
    assert job.error_message is None
    assert document.page_count is None


async def test_run_job_fails_when_pdf_has_no_text(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await _create_document_with_file(
        db_session,
        tmp_path,
        org_a,
        admin_a,
        content=build_scanned_pdf_bytes(page_count=3),
    )
    job = await create_processing_job(db_session, document)
    service = ProcessingService(db_session, LocalFileStorage(tmp_path))

    await service.run_job(document_id=document.id, job_id=job.id)

    assert job.status == JobStatus.FAILED
    assert job.error_message == PDF_NO_TEXT_MESSAGE
    assert document.status == DocumentStatus.FAILED


async def test_run_job_fails_when_pdf_is_corrupt(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await _create_document_with_file(
        db_session,
        tmp_path,
        org_a,
        admin_a,
        content=b"%PDF-1.7 archivo corrupto truncado",
    )
    job = await create_processing_job(db_session, document)
    service = ProcessingService(db_session, LocalFileStorage(tmp_path))

    await service.run_job(document_id=document.id, job_id=job.id)

    assert job.status == JobStatus.FAILED
    assert job.error_message == PDF_CORRUPT_MESSAGE
    assert document.status == DocumentStatus.FAILED


async def test_run_job_completes_with_extraction_warnings(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await _create_document_with_file(
        db_session, tmp_path, org_a, admin_a, content=b"contenido arbitrario del archivo"
    )
    job = await create_processing_job(db_session, document)
    service = ProcessingService(
        db_session,
        LocalFileStorage(tmp_path),
        extractors=(_ExtractorConAdvertencias(),),
    )

    await service.run_job(document_id=document.id, job_id=job.id)

    assert document.status == DocumentStatus.COMPLETED
    assert job.status == JobStatus.COMPLETED
    assert job.error_message is None


async def test_run_job_fails_when_mime_type_is_unsupported(
    db_session: AsyncSession, tmp_path, org_a: Organization, admin_a
) -> None:
    document = await _create_document_with_file(
        db_session,
        tmp_path,
        org_a,
        admin_a,
        content=b"contenido arbitrario del archivo",
        filename="archivo.otro",
        mime_type="application/x-otro",
    )
    job = await create_processing_job(db_session, document)
    service = ProcessingService(db_session, LocalFileStorage(tmp_path))

    await service.run_job(document_id=document.id, job_id=job.id)

    assert job.status == JobStatus.FAILED
    assert job.error_message == UNSUPPORTED_TYPE_MESSAGE
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
    content = build_pdf_bytes("Informe tecnico de la organizacion.")
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
    assert document_after.page_count == 1
