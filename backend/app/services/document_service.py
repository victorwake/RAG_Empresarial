"""Casos de uso de gestión documental."""

import logging
import uuid
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.context import TenantContext
from app.core.exceptions import ConflictError, NotFoundError, PayloadTooLargeError
from app.interfaces.queue import ProcessingQueue
from app.interfaces.storage import FileStorage
from app.models.document import Document
from app.models.enums import DocumentStatus, JobType
from app.repositories.document_repository import DocumentRepository
from app.repositories.processing_job_repository import ProcessingJobRepository
from app.services.file_validation import validate_upload

logger = logging.getLogger("app.documents")

DUPLICATE_DETAIL = "Ya existe un documento idéntico en la organización."
NOT_FOUND_DETAIL = "El documento solicitado no existe."
ACTIVE_JOB_DETAIL = "El documento ya tiene un trabajo de procesamiento activo."


class DocumentService:
    """Carga, consulta, borrado y reproceso de documentos por organización."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: FileStorage,
        queue: ProcessingQueue,
        settings: Settings,
    ) -> None:
        self._session = session
        self._storage = storage
        self._queue = queue
        self._settings = settings
        self._documents = DocumentRepository(session)
        self._jobs = ProcessingJobRepository(session)

    async def upload(self, *, file: UploadFile, context: TenantContext) -> Document:
        max_bytes = self._settings.max_upload_mb * 1024 * 1024
        if file.size is not None and file.size > max_bytes:
            raise PayloadTooLargeError(
                f"El archivo supera el límite de {self._settings.max_upload_mb} MB."
            )
        content = await file.read()
        validated = validate_upload(
            filename=file.filename,
            content_type=file.content_type,
            content=content,
            max_bytes=max_bytes,
            allowed_extensions=self._settings.allowed_extensions_list,
        )

        duplicate = await self._documents.get_by_checksum(
            context.organization_id, validated.checksum
        )
        if duplicate is not None:
            raise ConflictError(
                DUPLICATE_DETAIL, extra={"existing_document_id": str(duplicate.id)}
            )

        storage_path = await self._storage.save(
            context.organization_id, validated.content, validated.filename
        )
        document = await self._documents.create(
            organization_id=context.organization_id,
            uploaded_by=context.user_id,
            filename=validated.filename,
            original_filename=validated.original_filename,
            storage_path=storage_path,
            mime_type=validated.mime_type,
            file_size=len(validated.content),
            checksum=validated.checksum,
        )
        job = await self._jobs.create(
            document_id=document.id,
            organization_id=context.organization_id,
            job_type=JobType.INGEST,
        )
        await self._session.commit()
        logger.info(
            "documento_cargado",
            extra={
                "document_id": str(document.id),
                "file_size": document.file_size,
                "job_id": str(job.id),
            },
        )
        await self._queue.enqueue_ingestion(document.id, job.id)
        return document

    async def list_documents(
        self,
        *,
        context: TenantContext,
        limit: int,
        offset: int,
        status: DocumentStatus | None = None,
        search: str | None = None,
        uploaded_by: uuid.UUID | None = None,
    ) -> tuple[list[Document], int]:
        return await self._documents.list_for_organization(
            organization_id=context.organization_id,
            limit=limit,
            offset=offset,
            status=status,
            search=search,
            uploaded_by=uploaded_by,
        )

    async def get_document(
        self, *, context: TenantContext, document_id: uuid.UUID
    ) -> Document:
        document = await self._documents.get_by_id_and_organization(
            context.organization_id, document_id
        )
        if document is None:
            raise NotFoundError(NOT_FOUND_DETAIL)
        return document

    async def delete_document(
        self, *, context: TenantContext, document_id: uuid.UUID
    ) -> None:
        document = await self.get_document(context=context, document_id=document_id)
        storage_path = document.storage_path
        await self._documents.delete(document)
        await self._session.commit()
        await self._storage.delete(storage_path)
        logger.info(
            "documento_eliminado", extra={"document_id": str(document_id)}
        )

    async def reprocess_document(
        self, *, context: TenantContext, document_id: uuid.UUID
    ) -> Document:
        document = await self.get_document(context=context, document_id=document_id)
        active_job = await self._jobs.get_active_for_document(document.id)
        if active_job is not None:
            raise ConflictError(ACTIVE_JOB_DETAIL)
        job = await self._jobs.create(
            document_id=document.id,
            organization_id=context.organization_id,
            job_type=JobType.REPROCESS,
        )
        document.status = DocumentStatus.PENDING
        await self._session.commit()
        await self._session.refresh(document)
        logger.info(
            "documento_reencolado",
            extra={"document_id": str(document.id), "job_id": str(job.id)},
        )
        await self._queue.enqueue_reprocess(document.id, job.id)
        return document

    async def open_document_file(
        self, *, context: TenantContext, document_id: uuid.UUID
    ) -> tuple[Document, BinaryIO]:
        document = await self.get_document(context=context, document_id=document_id)
        file = await self._storage.open(document.storage_path)
        return document, file
