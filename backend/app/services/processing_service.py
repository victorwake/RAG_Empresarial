"""Casos de uso del procesamiento documental.

La extracción de texto se implementa en la Etapa 4; en la Etapa 3 el job
verifica el archivo y marca el documento ``COMPLETED`` (stub documentado en
ADR-017).
"""

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, ProcessingError
from app.database.session import session_scope
from app.interfaces.storage import FileStorage, LocalFileStorage
from app.models.document import Document
from app.models.enums import DocumentStatus, JobStatus
from app.models.processing_job import ProcessingJob
from app.repositories.document_repository import DocumentRepository
from app.repositories.processing_job_repository import ProcessingJobRepository

logger = logging.getLogger("app.processing")

DOCUMENT_DELETED_MESSAGE = "El documento fue eliminado antes de procesarse."
FILE_UNAVAILABLE_MESSAGE = (
    "El archivo del documento no está disponible en el almacenamiento."
)


class ProcessingService:
    """Ejecuta jobs de ingesta y reproceso con transiciones atómicas."""

    def __init__(self, session: AsyncSession, storage: FileStorage) -> None:
        self._session = session
        self._storage = storage
        self._documents = DocumentRepository(session)
        self._jobs = ProcessingJobRepository(session)

    async def run_job(self, *, document_id: uuid.UUID, job_id: uuid.UUID) -> None:
        job = await self._jobs.get_by_id(job_id)
        if job is None:
            logger.warning("job_inexistente", extra={"job_id": str(job_id)})
            return
        if job.status != JobStatus.PENDING:
            logger.info(
                "job_omitido_por_estado",
                extra={"job_id": str(job_id), "estado": job.status.value},
            )
            return

        claimed = await self._jobs.claim(job_id)
        if not claimed:
            return
        await self._session.refresh(job)

        document = await self._documents.get_by_id(document_id)
        if document is None:
            await self._fail(job, DOCUMENT_DELETED_MESSAGE)
            return

        try:
            await self._verify_file(document)
            await self._complete(job, document)
        except OSError:
            await self._fail(job, FILE_UNAVAILABLE_MESSAGE, document)
        except AppError as exc:
            await self._fail(job, str(exc), document)

    async def _verify_file(self, document: Document) -> None:
        file: BinaryIO = await self._storage.open(document.storage_path)
        try:
            if not file.read(1):
                raise ProcessingError("El archivo del documento está vacío o truncado.")
        finally:
            file.close()

    async def _complete(self, job: ProcessingJob, document: Document) -> None:
        now = datetime.now(UTC)
        job.status = JobStatus.COMPLETED
        job.completed_at = now
        document.status = DocumentStatus.COMPLETED
        await self._session.commit()
        logger.info(
            "job_completado",
            extra={
                "job_id": str(job.id),
                "document_id": str(document.id),
                "attempts": job.attempts,
            },
        )

    async def _fail(
        self, job: ProcessingJob, message: str, document: Document | None = None
    ) -> None:
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(UTC)
        job.error_message = message
        if document is not None:
            document.status = DocumentStatus.FAILED
        await self._session.commit()
        logger.warning(
            "job_fallido",
            extra={"job_id": str(job.id), "document_id": str(job.document_id), "error": message},
        )


async def run_processing_job(document_id: uuid.UUID, job_id: uuid.UUID) -> None:
    """Punto de entrada de la cola. Cada tarea usa su propia sesión."""
    settings = get_settings()
    storage = LocalFileStorage(Path(settings.file_storage_root))
    async with session_scope() as session:
        service = ProcessingService(session, storage)
        await service.run_job(document_id=document_id, job_id=job_id)


async def reconcile_orphan_jobs() -> tuple[int, int]:
    """Al arrancar, marca ``FAILED`` jobs y documentos huérfanos."""
    async with session_scope() as session:
        jobs = await ProcessingJobRepository(session).mark_stale_as_failed()
        documents = await DocumentRepository(session).mark_stale_as_failed()
    if jobs or documents:
        logger.info("jobs_reconciliados", extra={"jobs": jobs, "documentos": documents})
    return jobs, documents
