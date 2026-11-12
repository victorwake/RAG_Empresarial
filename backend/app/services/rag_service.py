"""Servicio RAG — orquesta recuperación, generación y persistencia.

Conecta la búsqueda semántica (Etapa 5) con el LLM (Etapa 6) para
generar respuestas contextualizadas con fuentes verificables.
"""

import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import MessageRole, MessageStatus
from app.models.message import Message
from app.models.message_source import MessageSource
from app.rag.embedding_provider import EmbeddingProvider
from app.rag.llm_provider import LLMProvider
from app.rag.prompt_builder import build_full_prompt
from app.repositories.document_chunk_repository import DocumentChunkRepository

logger = logging.getLogger("app.rag.service")

NO_INFO_ANSWER = (
    "No encontré información suficiente en la documentación disponible "
    "para responder esta consulta."
)


class RAGService:
    """Orquesta el pipeline RAG: retrieval → prompt → LLM → respuesta."""

    def __init__(
        self,
        session: AsyncSession,
        llm_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
        settings: Settings,
    ) -> None:
        self._session = session
        self._llm = llm_provider
        self._embeddings = embedding_provider
        self._settings = settings
        self._chunks = DocumentChunkRepository(session)

    async def ask(
        self,
        *,
        question: str,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
        document_ids: list[uuid.UUID] | None = None,
    ) -> "RAGResult":
        """Procesa una pregunta y devuelve una respuesta con fuentes.

        Flujo:
        1. Genera el embedding de la consulta.
        2. Busca chunks relevantes por similitud coseno.
        3. Si no hay contexto válido → NO_INFO sin llamar al LLM.
        4. Construye el prompt con contexto y llama al LLM.
        5. Valida la respuesta y las fuentes.
        6. Persiste conversación, mensajes y fuentes.
        """
        start = time.monotonic()

        # 1. Embedding de la consulta
        query_embedding = await self._embeddings.embed_query(question)

        # 2. Búsqueda semántica
        top_k = self._settings.retrieval_top_k
        min_score = self._settings.retrieval_min_score

        results = await self._chunks.search(
            organization_id=organization_id,
            query_embedding=query_embedding,
            document_ids=document_ids or None,
            top_k=top_k,
            min_score=min_score,
        )

        # 3. Política de "no información" — sin llamar al LLM
        if not results:
            logger.info(
                "rag_no_info_sin_candidatos",
                extra={
                    "user_id": str(user_id),
                    "organization_id": str(organization_id),
                    "question": question[:100],
                },
            )
            no_info_result = RAGResult.no_info(question)
            await self._persist_no_info(
                question=question,
                user_id=user_id,
                organization_id=organization_id,
                conversation_id=conversation_id,
                message=NO_INFO_ANSWER,
            )
            return no_info_result

        # 4. Construir prompt y llamar al LLM
        try:
            system_prompt, user_message = build_full_prompt(
                question=question,
                chunks_with_score=results,
                prompt_version=self._settings.prompt_version,
                max_context_tokens=self._settings.retrieval_max_context_tokens,
            )

            llm_response = await self._llm.generate(
                system_prompt=system_prompt,
                user_message=user_message,
                timeout_seconds=self._settings.llm_timeout_seconds,
            )

            # 5. Validar respuesta
            answer = llm_response.text.strip()
            status = self._determine_status(answer, results)

            # Construir fuentes
            sources = await self._build_sources(results)

            elapsed_ms = int((time.monotonic() - start) * 1000)

            rag_result = RAGResult(
                message_id=uuid.uuid4(),
                question=question,
                answer=answer,
                status=status,
                sources=sources,
                model=llm_response.model,
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                latency_ms=elapsed_ms,
                prompt_version=self._settings.prompt_version,
            )

            # 6. Persistir
            await self._persist_answered(
                rag_result=rag_result,
                user_id=user_id,
                organization_id=organization_id,
                conversation_id=conversation_id,
                chunks_with_score=results,
            )

            return rag_result

        except Exception as exc:
            logger.error(
                "rag_error_generando_respuesta",
                extra={
                    "user_id": str(user_id),
                    "error": str(exc),
                },
            )
            error_result = RAGResult.error(question, str(exc))
            await self._persist_error(
                question=question,
                user_id=user_id,
                organization_id=organization_id,
                conversation_id=conversation_id,
                error_message=str(exc),
            )
            return error_result

    def _determine_status(self, answer: str, results: list) -> MessageStatus:
        """Determina el estado de la respuesta."""
        no_info_phrases = [
            "no encontré información suficiente",
            "no hay información",
            "no aparece en la documentación",
        ]
        for phrase in no_info_phrases:
            if phrase in answer.lower():
                return MessageStatus.NO_INFO
        return MessageStatus.ANSWERED

    async def _build_sources(
        self, results: list[tuple[DocumentChunk, float]]
    ) -> list["SourceInfo"]:
        """Construye la lista de fuentes con metadatos del documento."""
        sources: list[SourceInfo] = []
        for rank, (chunk, score) in enumerate(results, start=1):
            # Buscar el nombre del documento
            doc = await self._get_document_name(chunk.document_id)
            sources.append(
                SourceInfo(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    filename=doc,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    relevance_score=round(score, 4),
                    rank=rank,
                )
            )
        return sources

    async def _get_document_name(self, document_id: uuid.UUID) -> str:
        """Obtiene el nombre del documento por su ID."""
        stmt = select(Document.filename).where(Document.id == document_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row or f"documento-{document_id}"

    async def _persist_no_info(
        self,
        *,
        question: str,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        message: str,
    ) -> None:
        """Persiste una respuesta NO_INFO."""
        if conversation_id is None:
            conversation_id = await self._create_conversation(
                user_id=user_id,
                organization_id=organization_id,
                title=question[:200],
            )

        # Mensaje del usuario
        user_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=question,
        )
        self._session.add(user_msg)

        # Respuesta del asistente
        assistant_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=message,
            status=MessageStatus.NO_INFO,
        )
        self._session.add(assistant_msg)

        await self._session.flush()

    async def _persist_answered(
        self,
        *,
        rag_result: "RAGResult",
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        chunks_with_score: list[tuple[DocumentChunk, float]],
    ) -> None:
        """Persiste una respuesta ANSWERED con fuentes."""
        if conversation_id is None:
            conversation_id = await self._create_conversation(
                user_id=user_id,
                organization_id=organization_id,
                title=rag_result.question[:200],
            )

        # Mensaje del usuario
        user_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=rag_result.question,
        )
        self._session.add(user_msg)

        # Respuesta del asistente
        assistant_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=rag_result.answer,
            status=rag_result.status,
            model=rag_result.model,
            prompt_tokens=rag_result.prompt_tokens,
            completion_tokens=rag_result.completion_tokens,
            latency_ms=rag_result.latency_ms,
        )
        self._session.add(assistant_msg)
        await self._session.flush()
        assistant_msg_id = assistant_msg.id

        # Fuentes
        for source in rag_result.sources:
            ms = MessageSource(
                message_id=assistant_msg_id,
                chunk_id=source.chunk_id,
                rank=source.rank,
                relevance_score=source.relevance_score,
            )
            self._session.add(ms)

        await self._session.flush()

    async def _persist_error(
        self,
        *,
        question: str,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        error_message: str,
    ) -> None:
        """Persiste una respuesta ERROR."""
        if conversation_id is None:
            conversation_id = await self._create_conversation(
                user_id=user_id,
                organization_id=organization_id,
                title=question[:200],
            )

        user_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=question,
        )
        self._session.add(user_msg)

        assistant_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=f"Error al procesar la consulta: {error_message}",
            status=MessageStatus.ERROR,
        )
        self._session.add(assistant_msg)

        await self._session.flush()

    async def _create_conversation(
        self,
        *,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        title: str,
    ) -> uuid.UUID:
        """Crea una nueva conversación y devuelve su ID."""
        conv = Conversation(
            user_id=user_id,
            organization_id=organization_id,
            title=title,
        )
        self._session.add(conv)
        await self._session.flush()
        return conv.id


class SourceInfo:
    """Información de una fuente citada en la respuesta."""

    def __init__(
        self,
        *,
        chunk_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
        chunk_index: int,
        page_number: int | None,
        section: str | None,
        relevance_score: float,
        rank: int,
    ) -> None:
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.filename = filename
        self.chunk_index = chunk_index
        self.page_number = page_number
        self.section = section
        self.relevance_score = relevance_score
        self.rank = rank


class RAGResult:
    """Resultado del pipeline RAG."""

    def __init__(
        self,
        *,
        message_id: uuid.UUID,
        question: str,
        answer: str,
        status: MessageStatus,
        sources: list[SourceInfo],
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        prompt_version: str,
    ) -> None:
        self.message_id = message_id
        self.question = question
        self.answer = answer
        self.status = status
        self.sources = sources
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.latency_ms = latency_ms
        self.prompt_version = prompt_version

    @staticmethod
    def no_info(question: str) -> "RAGResult":
        return RAGResult(
            message_id=uuid.uuid4(),
            question=question,
            answer=NO_INFO_ANSWER,
            status=MessageStatus.NO_INFO,
            sources=[],
            model="",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
            prompt_version="",
        )

    @staticmethod
    def error(question: str, error_message: str) -> "RAGResult":
        return RAGResult(
            message_id=uuid.uuid4(),
            question=question,
            answer=f"Error: {error_message}",
            status=MessageStatus.ERROR,
            sources=[],
            model="",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
            prompt_version="",
        )
