"""Repositorio de fragmentos con búsqueda semántica por vector."""

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk


class DocumentChunkRepository:
    """CRUD y búsqueda semántica de ``DocumentChunk``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    async def insert_many(self, chunks: list[DocumentChunk]) -> None:
        """Inserta varios chunks en una sola operación."""
        if chunks:
            self._session.add_all(chunks)

    async def delete_by_document(self, document_id: uuid.UUID) -> int:
        """Elimina todos los chunks de un documento (reproceso)."""
        from sqlalchemy import delete

        result = await self._session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        return result.rowcount or 0

    async def list_by_document(
        self,
        *,
        document_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DocumentChunk], int]:
        """Lista los chunks de un documento con paginación."""
        total = (
            (
                await self._session.scalar(
                    select(func.count())
                    .select_from(DocumentChunk)
                    .where(DocumentChunk.document_id == document_id)
                )
            )
            or 0
        )
        result = await self._session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    # ------------------------------------------------------------------
    # Búsqueda semántica
    # ------------------------------------------------------------------

    async def search(
        self,
        *,
        organization_id: uuid.UUID,
        query_embedding: list[float],
        document_ids: list[uuid.UUID] | None = None,
        top_k: int = 6,
        min_score: float = 0.35,
    ) -> list[tuple[DocumentChunk, float]]:
        """Busca chunks por similitud coseno con el embedding de consulta.

        Args:
            organization_id: Filtro obligatorio por organización.
            query_embedding: Vector de la consulta.
            document_ids: Opcional — restringir a documentos específicos.
            top_k: Cantidad máxima de candidatos.
            min_score: Umbral mínimo de similitud coseno (0–1).

        Returns:
            Lista de ``(chunk, score)`` ordenada por score descendente.
        """
        # Construir la consulta completa como text() para evitar problemas de tipo
        # La lista de floats es segura: solo contiene números, no input del usuario
        vec_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"

        sql = f"""
            SELECT document_chunks.*,
                   1 - (document_chunks.embedding <=> '{vec_literal}'::vector) AS score
            FROM document_chunks
            WHERE document_chunks.organization_id = :org_id
              AND (1 - (document_chunks.embedding <=> '{vec_literal}'::vector)) >= :min_score
            ORDER BY score DESC
            LIMIT :top_k
        """  # noqa: S608

        stmt = text(sql).bindparams(
            org_id=organization_id, min_score=min_score, top_k=top_k
        )

        result = await self._session.execute(stmt)
        rows = result.fetchall()
        columns = result.keys()

        # Convertir filas a objetos DocumentChunk + score
        chunk_list: list[tuple[DocumentChunk, float]] = []
        for row in rows:
            data = dict(zip(columns, row, strict=False))
            chunk = DocumentChunk(**{k: v for k, v in data.items() if k != "score"})
            chunk_list.append((chunk, float(data["score"])))

        return chunk_list
