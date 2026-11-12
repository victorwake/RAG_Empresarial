"""Casos de uso del procesamiento documental.

Ejecuta la extracción de texto, chunking y generación de embeddings
(Etapas 4–5). Los chunks se persisten en ``document_chunks`` con sus
vectores en pgvector.
"""

import asyncio
import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

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
from app.document_processing.base import ensure_extractable
from app.document_processing.normalizer import normalize_text
from app.interfaces.storage import FileStorage, LocalFileStorage
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus, JobStatus
from app.models.processing_job import ProcessingJob
from app.rag.chunker import chunk_text
from app.rag.embedding_provider import EmbeddingError, EmbeddingProvider
from app.rag.gemini_embedding import GeminiEmbeddingProvider
from app.repositories.document_chunk_repository import DocumentChunkRepository
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
    """Ejecuta jobs de ingesta y reproceso con transiciones atómicas.

    Integra extracción de texto (Etapa 4), chunking y embeddings (Etapa 5).
    """

    def __init__(
        self,
        session: AsyncSession,
        storage: FileStorage,
        extractors: Sequence[TextExtractor] = DEFAULT_EXTRACTORS,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._session = session
        self._storage = storage
        self._extractors = tuple(extractors)
        self._embedding_provider = embedding_provider
        self._documents = DocumentRepository(session)
        self._jobs = ProcessingJobRepository(session)
        self._chunks = DocumentChunkRepository(session)

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
            await self._chunk_and_embed(job, document, result)
        except OSError:
            await self._fail(job, FILE_UNAVAILABLE_MESSAGE, document)
        except AppError as exc:
            await self._fail(job, str(exc), document)

    async def _read_file(self, document: Document) -> bytes:
        from typing import BinaryIO

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

    async def _chunk_and_embed(
        self, job: ProcessingJob, document: Document, result: ExtractionResult
    ) -> None:
        """Chunking, embeddings y persistencia de fragmentos (Etapa 5)."""
        settings = get_settings()

        # Normalizar el texto extraído
        text = normalize_text(result.text)
        ensure_extractable(text)

        # Construir números de página por párrafo (si el extractor los proporcionó)
        page_numbers: list[int] | None = None
        if result.pages:
            # Dividir por párrafos y asignar página del primer párrafo
            page_numbers = [p.page_number for p in result.pages]

        # Chunking
        chunks = chunk_text(
            text,
            page_numbers=page_numbers,
            chunk_size=settings.chunk_size_tokens,
            overlap=settings.chunk_overlap_tokens,
        )

        if not chunks:
            await self._complete(job, document, result)
            return

        # Generar embeddings
        provider = self._embedding_provider or GeminiEmbeddingProvider.from_settings()
        contents = [c.content for c in chunks]
        try:
            embeddings = await provider.embed_documents(contents)
        except EmbeddingError as exc:
            raise ProcessingError(
                f"No se pudieron generar los embeddings: {exc}"
            ) from exc

        # Validar dimensiones
        if embeddings and len(embeddings[0]) != settings.embedding_dimension:
            raise ProcessingError(
                f"Dimensión de embedding incorrecta: "
                f"se esperaba {settings.embedding_dimension}, "
                f"se obtuvo {len(embeddings[0])}."
            )

        # Eliminar chunks previos (reproceso idempotente)
        deleted = await self._chunks.delete_by_document(document.id)
        if deleted:
            logger.info(
                "chunks_previos_eliminados",
                extra={"document_id": str(document.id), "deleted": deleted},
            )

        # Construir entidades DocumentChunk
        chunk_entities = []
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            entity = DocumentChunk(
                document_id=document.id,
                organization_id=document.organization_id,
                chunk_index=chunk.index,
                content=chunk.content,
                embedding=embedding,
                embedding_model=provider.model_name,
                page_number=chunk.page_number,
                section=chunk.section,
                metadata={
                    "token_count": chunk.token_count,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "content_hash": chunk.content_hash,
                    "embedding_model": provider.model_name,
                    "source_format": document.mime_type,
                },
            )
            chunk_entities.append(entity)

        # Persistir chunks
        await self._chunks.insert_many(chunk_entities)

        now = datetime.now(UTC)
        job.status = JobStatus.COMPLETED
        job.completed_at = now
        document.status = DocumentStatus.COMPLETED
        document.page_count = result.page_count
        await self._session.commit()

        logger.info(
            "job_completado_con_chunks",
            extra={
                "job_id": str(job.id),
                "document_id": str(document.id),
                "attempts": job.attempts,
                "page_count": result.page_count,
                "chunk_count": len(chunk_entities),
                "embedding_model": provider.model_name,
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

    async def _complete(
        self, job: ProcessingJob, document: Document, result: ExtractionResult
    ) -> None:
        """Completa el job sin chunks (ruta de respaldo para texto vacío)."""
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
