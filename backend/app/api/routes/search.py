"""Rutas de búsqueda semántica."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_embedding_provider, get_tenant_context
from app.core.config import Settings, get_settings
from app.core.context import TenantContext
from app.rag.embedding_provider import EmbeddingProvider
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.schemas.chunk import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    SearchSource,
)

logger = logging.getLogger("app.search")

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    """Busca fragmentos relevantes por similitud semántica.

    Genera el embedding de la consulta, busca en pgvector con filtro
    por organización y umbral configurable, y devuelve los chunks
    ordenados por score.
    """
    repo = DocumentChunkRepository(session)

    top_k = request.top_k or settings.retrieval_top_k
    min_score = settings.retrieval_min_score

    # Generar embedding de la consulta
    query_embedding = await provider.embed_query(request.query)

    # Buscar chunks relevantes
    results = await repo.search(
        organization_id=context.organization_id,
        query_embedding=query_embedding,
        document_ids=request.document_ids or None,
        top_k=top_k,
        min_score=min_score,
    )

    # Construir respuesta
    sources = [
        SearchSource(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            page_number=chunk.page_number,
            section=chunk.section,
            score=round(score, 4),
        )
        for chunk, score in results
    ]

    status = "ANSWERED" if sources else "NO_INFO"

    search_result = SearchResult(
        query=request.query,
        sources=sources,
        total=len(sources),
        top_k=top_k,
        min_score=min_score,
        status=status,
    )

    logger.info(
        "búsqueda_ejecutada",
        extra={
            "organization_id": str(context.organization_id),
            "user_id": str(context.user_id),
            "query": request.query[:100],
            "top_k": top_k,
            "min_score": min_score,
            "results": len(sources),
            "status": status,
        },
    )

    return SearchResponse(result=search_result)
