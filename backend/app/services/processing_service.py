"""Casos de uso del procesamiento documental.

Ejecuta la extracción de texto real con los extractores de
``app.document_processing`` (Etapa 4). El texto extraído es transitorio: no se
persiste porque los chunks de la Etapa 5 serán la representación derivada
(ADR-018).
"""

import asyncio
import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, ProcessingError
from app.database.session import session_scope
from app.document_processing import (
    DEFAULT_EXTRACTORS,
    ExtractionResult,
    TextExtractor,
    find_extractor,
)
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
EMPTY_FILE_MESSAGE = "El archivo del documento está vacío o truncado."
UNSUPPORTED_TYPE_MESSAGE = "El tipo de documento no es soportado para extracción."


class ProcessingService:
    """Ejecuta jobs de ingesta y reproceso con transiciones atómicas."""

    def __init__(
        self,
        session: AsyncSession,
        storage: FileStorage,
        extractors: Sequence[TextExtractor] = DEFAULT_EXTRACTORS,
    ) -> None:
        self._session = session
        self._storage = storage
        self._extractors = tuple(extractors)
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
            content = await self._read_file(document)
            result = await self._extract(document, content)
            await self._complete(job, document, result)
        except OSError:
            await self._fail(job, FILE_UNAVAILABLE_MESSAGE, document)
        except AppError as exc:
            await self._fail(job, str(exc), document)

    async def _read_file(self, document: Document) -> bytes:
        file: BinaryIO = await self._storage.open(document.storage_path)
        try:
            content = await asyncio.to_thread(file.read)
        finally:
            file.close()
        if not content:
            raise ProcessingError(EMPTY_FILE_MESSAGE)
        return content

    async def _extract(self, document: Document, content: bytes) -> ExtractionResult:
        extractor = find_extractor(self._extractors, document.mime_type)
        if extractor is None:
            raise ProcessingError(UNSUPPORTED_TYPE_MESSAGE)
        return await asyncio.to_thread(extractor.extract, content)

    async def _complete(
        self, job: ProcessingJob, document: Document, result: ExtractionResult
    ) -> None:
        now = datetime.now(UTC)
        job.status = JobStatus.COMPLETED
        job.completed_at = now
        document.status = DocumentStatus.COMPLETED
        document.page_count = result.page_count
        await self._session.commit()
        logger.info(
            "job_completado",
            extra={
                "job_id": str(job.id),
                "document_id": str(document.id),
                "attempts": job.attempts,
                "page_count": result.page_count,
            },
        )
        if result.warnings:
            logger.warning(
                "extraccion_con_advertencias",
                extra={
                    "document_id": str(document.id),
                    "warnings": list(result.warnings),
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
            extra={
                "job_id": str(job.id),
                "document_id": str(job.document_id),
                "error": message,
            },
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
