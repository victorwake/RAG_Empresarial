"""Schemas de respuesta para el endpoint de chat RAG."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ChatSource(BaseModel):
    """Fuente citada en la respuesta."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    page_number: int | None = None
    section: str | None = None
    relevance_score: float


class ChatResponse(BaseModel):
    """Respuesta del endpoint de chat."""

    message_id: uuid.UUID
    question: str
    answer: str
    status: str  # ANSWERED, NO_INFO, ERROR
    sources: list[ChatSource]
    model: str
    latency_ms: int


class ChatRequest(BaseModel):
    """Solicitud de chat del usuario."""

    question: str
    conversation_id: uuid.UUID | None = None
    document_ids: list[uuid.UUID] | None = None


class ConversationSummary(BaseModel):
    """Resumen de una conversación listada."""

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationsListResponse(BaseModel):
    """Lista de conversaciones del usuario."""

    conversations: list[ConversationSummary]
    total: int


class MessageItem(BaseModel):
    """Mensaje individual en el historial."""

    id: uuid.UUID
    role: str
    content: str
    status: str | None = None
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    """Detalle de una conversación con sus mensajes."""

    id: uuid.UUID
    title: str
    messages: list[MessageItem]
