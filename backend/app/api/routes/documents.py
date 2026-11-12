"""Rutas de gestión documental."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import BinaryIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_db,
    get_file_storage,
    get_processing_queue,
    get_tenant_context,
    require_admin,
)
from app.core.config import Settings, get_settings
from app.core.context import TenantContext
from app.interfaces.queue import ProcessingQueue
from app.interfaces.storage import FileStorage
from app.models.enums import DocumentStatus
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.schemas.chunk import ChunkListResponse, ChunkResponse
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.document_service import DocumentService

NOT_FOUND_DETAIL = "El documento solicitado no existe."

router = APIRouter(prefix="/documents", tags=["documents"])

DOWNLOAD_CHUNK_SIZE = 64 * 1024


def _service(
    session: AsyncSession,
    *,
    storage: FileStorage,
    queue: ProcessingQueue,
    settings: Settings,
) -> DocumentService:
    return DocumentService(session, storage=storage, queue=queue, settings=settings)


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    context: TenantContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
    queue: ProcessingQueue = Depends(get_processing_queue),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    service = _service(session, storage=storage, queue=queue, settings=settings)
    document = await service.upload(file=file, context=context)
    return document


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
    queue: ProcessingQueue = Depends(get_processing_queue),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: DocumentStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, min_length=1, max_length=255),
    uploaded_by: uuid.UUID | None = None,
) -> DocumentListResponse:
    service = _service(session, storage=storage, queue=queue, settings=settings)
    documents, total = await service.list_documents(
        context=context,
        limit=limit,
        offset=offset,
        status=status_filter,
        search=search,
        uploaded_by=uploaded_by,
    )
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(document) for document in documents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
    queue: ProcessingQueue = Depends(get_processing_queue),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    service = _service(session, storage=storage, queue=queue, settings=settings)
    return await service.get_document(context=context, document_id=document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    context: TenantContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
    queue: ProcessingQueue = Depends(get_processing_queue),
    settings: Settings = Depends(get_settings),
) -> Response:
    service = _service(session, storage=storage, queue=queue, settings=settings)
    await service.delete_document(context=context, document_id=document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{document_id}/reprocess",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentResponse,
)
async def reprocess_document(
    document_id: uuid.UUID,
    context: TenantContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
    queue: ProcessingQueue = Depends(get_processing_queue),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    service = _service(session, storage=storage, queue=queue, settings=settings)
    return await service.reprocess_document(context=context, document_id=document_id)


@router.get("/{document_id}/file")
async def download_document_file(
    document_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
    queue: ProcessingQueue = Depends(get_processing_queue),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    service = _service(session, storage=storage, queue=queue, settings=settings)
    document, file = await service.open_document_file(
        context=context, document_id=document_id
    )
    disposition = f"attachment; filename*=UTF-8''{quote(document.original_filename, safe='')}"
    return StreamingResponse(
        _stream_file(file),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": disposition,
            "Content-Length": str(document.file_size),
        },
    )


async def _stream_file(file: BinaryIO) -> AsyncIterator[bytes]:
    try:
        while chunk := await asyncio.to_thread(file.read, DOWNLOAD_CHUNK_SIZE):
            yield chunk
    finally:
        await asyncio.to_thread(file.close)


@router.get("/{document_id}/chunks", response_model=ChunkListResponse)
async def list_chunks(
    document_id: uuid.UUID,
    context: TenantContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
    queue: ProcessingQueue = Depends(get_processing_queue),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ChunkListResponse:
    """Lista los fragmentos generados para un documento (uso diagnóstico)."""
    service = _service(session, storage=storage, queue=queue, settings=settings)
    await service.get_document(context=context, document_id=document_id)

    repo = DocumentChunkRepository(session)
    chunks, total = await repo.list_by_document(
        document_id=document_id, limit=limit, offset=offset
    )
    return ChunkListResponse(
        items=[ChunkResponse.model_validate(chunk) for chunk in chunks],
        total=total,
        limit=limit,
        offset=offset,
    )
