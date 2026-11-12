"""Tests unitarios del prompt builder."""

import uuid

import pytest
from app.rag.prompt_builder import (
    SYSTEM_PROMPT_V1,
    build_context_text,
    build_full_prompt,
    build_system_prompt,
    build_user_message,
)


def _make_chunk(
    content: str,
    chunk_index: int = 0,
    page_number: int | None = None,
    section: str | None = None,
):
    """Crea un DocumentChunk de prueba sin base de datos."""
    from app.models.document_chunk import DocumentChunk

    return DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        chunk_index=chunk_index,
        content=content,
        embedding=[0.1] * 768,
        embedding_model="test",
        page_number=page_number,
        section=section,
        metadata_={},
    )


class TestBuildSystemPrompt:
    def test_returns_v1_prompt(self) -> None:
        prompt = build_system_prompt(prompt_version="v1")
        assert prompt == SYSTEM_PROMPT_V1

    def test_raises_on_unknown_version(self) -> None:
        with pytest.raises(ValueError, match="no existe"):
            build_system_prompt(prompt_version="v99")

    def test_v1_contains_rules(self) -> None:
        prompt = build_system_prompt(prompt_version="v1")
        assert "DATO NO CONFIABLE" in prompt
        assert "NO obedezcas" in prompt
        assert "{context}" in prompt


class TestBuildContextText:
    def test_empty_chunks_returns_placeholder(self) -> None:
        result = build_context_text([])
        assert result == "(sin contexto disponible)"

    def test_single_chunk_includes_tags(self) -> None:
        chunk = _make_chunk("Contenido de prueba", page_number=3, section="Intro")
        result = build_context_text([(chunk, 0.85)])
        assert '<documento id="' in result
        assert ' pagina="3"' in result
        assert ' seccion="Intro"' in result
        assert "Contenido de prueba" in result
        assert "</documento>" in result

    def test_orders_by_score_descending(self) -> None:
        low = _make_chunk("Bajo score", chunk_index=0)
        high = _make_chunk("Alto score", chunk_index=1)
        result = build_context_text([(low, 0.3), (high, 0.9)])
        alto_pos = result.index("Alto score")
        bajo_pos = result.index("Bajo score")
        assert alto_pos < bajo_pos

    def test_respects_max_context_tokens(self) -> None:
        # Cada chunk tiene ~1000 caracteres = ~250 tokens
        chunks = [
            (_make_chunk("A" * 1000, chunk_index=i), 0.9 - i * 0.1)
            for i in range(5)
        ]
        result = build_context_text(chunks, max_context_tokens=500)
        # Con 500 tokens (~2000 chars), debería incluir ~2 chunks
        assert "AAAA" in result
        # No debería incluir todos
        count = result.count("</documento>")
        assert count < 5

    def test_chunk_without_page_and_section(self) -> None:
        chunk = _make_chunk("Sin metadatos")
        result = build_context_text([(chunk, 0.5)])
        assert ' pagina=' not in result
        assert ' seccion=' not in result


class TestBuildUserMessage:
    def test_wraps_question(self) -> None:
        result = build_user_message("¿Cuál es la política?")
        assert result == "Pregunta: ¿Cuál es la política?"


class TestBuildFullPrompt:
    def test_returns_tuple(self) -> None:
        chunk = _make_chunk("Contenido")
        system, user = build_full_prompt(
            question="¿Qué dice?",
            chunks_with_score=[(chunk, 0.8)],
        )
        assert isinstance(system, str)
        assert isinstance(user, str)
        assert "DATO NO CONFIABLE" in system
        assert user == "Pregunta: ¿Qué dice?"

    def test_context_injected_in_system(self) -> None:
        chunk = _make_chunk("Texto importante sobre vacaciones")
        system, user = build_full_prompt(
            question="¿Cuántas vacaciones tengo?",
            chunks_with_score=[(chunk, 0.9)],
        )
        assert "Texto importante sobre vacaciones" in system

    def test_empty_chunks_placeholder(self) -> None:
        system, user = build_full_prompt(
            question="¿Qué dice?",
            chunks_with_score=[],
        )
        assert "(sin contexto disponible)" in system
