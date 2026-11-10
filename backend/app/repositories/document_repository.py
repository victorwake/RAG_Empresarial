"""Repositorio de documentos. Toda consulta incluye la organización del token."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.enums import DocumentStatus


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        return await self._session.get(Document, document_id)

    async def get_by_id_and_organization(
        self, organization_id: uuid.UUID, document_id: uuid.UUID
    ) -> Document | None:
        result = await self._session.execute(
            select(Document).where(
                Document.organization_id == organization_id,
                Document.id == document_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_checksum(
        self, organization_id: uuid.UUID, checksum: str
    ) -> Document | None:
        result = await self._session.execute(
            select(Document).where(
                Document.organization_id == organization_id,
                Document.checksum == checksum,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        uploaded_by: uuid.UUID,
        filename: str,
        original_filename: str,
        storage_path: str,
        mime_type: str,
        file_size: int,
        checksum: str,
    ) -> Document:
        document = Document(
            organization_id=organization_id,
            uploaded_by=uploaded_by,
            filename=filename,
            original_filename=original_filename,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=file_size,
            checksum=checksum,
        )
        self._session.add(document)
        await self._session.flush()
        return document

    async def list_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        limit: int,
        offset: int,
        status: DocumentStatus | None = None,
        search: str | None = None,
        uploaded_by: uuid.UUID | None = None,
    ) -> tuple[list[Document], int]:
        conditions = [Document.organization_id == organization_id]
        if status is not None:
            conditions.append(Document.status == status)
        if uploaded_by is not None:
            conditions.append(Document.uploaded_by == uploaded_by)
        if search:
            conditions.append(
                Document.filename.ilike(f"%{_escape_like(search)}%", escape="\\")
            )

        total = (
            await self._session.scalar(
                select(func.count()).select_from(Document).where(*conditions)
            )
            or 0
        )
        result = await self._session.execute(
            select(Document)
            .where(*conditions)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def delete(self, document: Document) -> None:
        await self._session.delete(document)

    async def mark_stale_as_failed(self) -> int:
        """Marca ``FAILED`` los documentos quedados en ``PENDING``/``PROCESSING``."""
        result = await self._session.execute(
            update(Document)
            .where(Document.status.in_((DocumentStatus.PENDING, DocumentStatus.PROCESSING)))
            .values(status=DocumentStatus.FAILED)
        )
        return result.rowcount
