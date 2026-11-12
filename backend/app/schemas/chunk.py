"""Schemas de fragmentos y búsqueda semántica."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChunkResponse(BaseModel):
    """Fragmento devuelto en la API (sin el vector)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    embedding_model: str
    page_number: int | None = None
    section: str | None = None
    metadata: dict = {}
    created_at: datetime


class ChunkListResponse(BaseModel):
    items: list[ChunkResponse]
    total: int
    limit: int
    offset: int


class SearchSource(BaseModel):
    """Fuente citada en un resultado de búsqueda."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int | None = None
    section: str | None = None
    score: float


class SearchRequest(BaseModel):
    """Solicitud de búsqueda semántica."""

    query: str
    document_ids: list[uuid.UUID] | None = None
    top_k: int | None = None


class SearchResult(BaseModel):
    """Resultado de una búsqueda semántica."""

    query: str
    sources: list[SearchSource]
    total: int
    top_k: int
    min_score: float
    status: str  # "ANSWERED" | "NO_INFO"


class SearchResponse(BaseModel):
    result: SearchResult
