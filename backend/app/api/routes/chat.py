"""Rutas de chat conversacional RAG.

Endpoints para hacer preguntas al sistema RAG y gestionar conversaciones.
"""

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_db,
    get_embedding_provider,
    get_llm_provider,
    get_tenant_context,
)
from app.core.config import Settings, get_settings
from app.core.context import TenantContext
from app.models.conversation import Conversation
from app.models.message import Message
from app.rag.embedding_provider import EmbeddingProvider
from app.rag.llm_provider import LLMProvider
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatSource,
    ConversationDetailResponse,
    ConversationsListResponse,
    ConversationSummary,
    MessageItem,
)
from app.services.rag_service import RAGService

logger = logging.getLogger("app.chat")

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    """Hace una pregunta al sistema RAG y recibe una respuesta con fuentes.

    El sistema busca fragmentos relevantes en la documentación de la
    organización y genera una respuesta contextualizada usando un LLM.
    Si no encuentra información, responde con NO_INFO sin llamar al LLM.
    """
    service = RAGService(
        session=session,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        settings=settings,
    )

    result = await service.ask(
        question=request.question,
        user_id=context.user_id,
        organization_id=context.organization_id,
        conversation_id=request.conversation_id,
        document_ids=request.document_ids,
    )

    sources = [
        ChatSource(
            chunk_id=s.chunk_id,
            document_id=s.document_id,
            filename=s.filename,
            chunk_index=s.chunk_index,
            page_number=s.page_number,
            section=s.section,
            relevance_score=s.relevance_score,
        )
        for s in result.sources
    ]

    logger.info(
        "rag_respuesta_generada",
        extra={
            "user_id": str(context.user_id),
            "organization_id": str(context.organization_id),
            "question": request.question[:100],
            "status": result.status.value,
            "sources": len(sources),
            "latency_ms": result.latency_ms,
            "model": result.model,
        },
    )

    return ChatResponse(
        message_id=result.message_id,
        question=result.question,
        answer=result.answer,
        status=result.status.value,
        sources=sources,
        model=result.model,
        latency_ms=result.latency_ms,
    )


@router.get("/conversations", response_model=ConversationsListResponse)
async def list_conversations(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_db),
) -> ConversationsListResponse:
    """Lista las conversaciones del usuario autenticado."""
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == context.user_id,
            Conversation.organization_id == context.organization_id,
        )
        .order_by(Conversation.updated_at.desc())
    )
    result = await session.execute(stmt)
    conversations = result.scalars().all()

    items = [
        ConversationSummary(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in conversations
    ]

    return ConversationsListResponse(conversations=items, total=len(items))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """Obtiene el detalle de una conversación con sus mensajes."""
    # Verificar que la conversación pertenece al usuario
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == context.user_id,
        Conversation.organization_id == context.organization_id,
    )
    result = await session.execute(stmt)
    conversation = result.scalar_one_or_none()
    if conversation is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Conversación no encontrada.")

    # Obtener mensajes ordenados
    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    msg_result = await session.execute(msg_stmt)
    messages = msg_result.scalars().all()

    items = [
        MessageItem(
            id=m.id,
            role=m.role.value if hasattr(m.role, "value") else m.role,
            content=m.content,
            status=m.status.value if m.status and hasattr(m.status, "value") else m.status,
            created_at=m.created_at,
        )
        for m in messages
    ]

    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        messages=items,
    )
