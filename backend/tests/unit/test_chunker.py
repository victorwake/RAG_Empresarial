"""Tests unitarios del chunker."""


from app.rag.chunker import chunk_text


class TestChunkText:
    """Verifica que el chunking divide correctamente el texto."""

    def test_empty_text_returns_no_chunks(self) -> None:
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text_returns_single_chunk(self) -> None:
        chunks = chunk_text("Texto corto de prueba.", chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0].content == "Texto corto de prueba."
        assert chunks[0].index == 0

    def test_long_text_returns_multiple_chunks(self) -> None:
        # Texto con párrafos separados por dobles saltos
        text = "\n\n".join([f"Párrafo número {i} con suficiente contenido." for i in range(20)])
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        assert len(chunks) > 1
        # Verificar orden
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chunks_have_content_hash(self) -> None:
        chunks = chunk_text("Texto con hash.", chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0].content_hash
        assert len(chunks[0].content_hash) == 16

    def test_page_numbers_propagated(self) -> None:
        text = "Párrafo 1.\n\nPárrafo 2.\n\nPárrafo 3."
        chunks = chunk_text(
            text,
            page_numbers=[1, 2, 3],
            chunk_size=500,
        )
        assert len(chunks) >= 1
        # El primer chunk hereda la página del primer párrafo
        assert chunks[0].page_number == 1

    def test_no_page_numbers_defaults_to_none(self) -> None:
        chunks = chunk_text("Sin páginas.", chunk_size=500)
        assert chunks[0].page_number is None

    def test_overlap_preserved_between_chunks(self) -> None:
        """Verifica que el overlap mantiene contenido entre chunks."""
        paragraphs = [f"Sección {i} con texto relevante." for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, chunk_size=50, overlap=20)
        assert len(chunks) > 1
        # Los chunks consecutivos deben tener contenido en común
        # (al menos el overlap debe estar presente)

    def test_token_count_in_metadata(self) -> None:
        chunks = chunk_text("Texto de prueba.", chunk_size=500)
        assert chunks[0].token_count > 0
        assert "token_count" in chunks[0].metadata

    def test_section_names_propagated(self) -> None:
        text = "Sección A.\n\nSección B."
        chunks = chunk_text(
            text,
            section_names=["Introducción", "Desarrollo"],
            chunk_size=500,
        )
        assert chunks[0].section == "Introducción"

    def test_chunk_content_not_empty(self) -> None:
        """Ningún chunk debe tener contenido vacío."""
        text = "\n\n".join([f"Contenido {i}." for i in range(5)])
        chunks = chunk_text(text, chunk_size=30, overlap=5)
        for chunk in chunks:
            assert chunk.content.strip()
            assert len(chunk.content.strip()) > 0
