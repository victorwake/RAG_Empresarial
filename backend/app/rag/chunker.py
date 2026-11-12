"""División de texto en chunks por tokens con overlap configurable."""

import hashlib
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("app.chunking")


@dataclass(frozen=True, slots=True)
class Chunk:
    """Fragmento de texto listo para embedding."""

    index: int
    content: str
    page_number: int | None
    section: str | None
    token_count: int
    char_start: int
    char_end: int
    content_hash: str
    metadata: dict[str, object] = field(default_factory=dict)


def _count_tokens(text: str) -> int:
    """Estima la cantidad de tokens usando una aproximación por palabras.

    Para el modelo Gemini text-embedding-004, 1 token ≈ 4 caracteres en
    promedio. Esta aproximación es conservadora y suficiente para el
    chunking; no requiere un tokenizador externo.
    """
    # Aproximación: cada 4 caracteres ≈ 1 token (clásico para BPE)
    return max(1, len(text) // 4)


def _estimate_tokens(text: str) -> int:
    """Estimación rápida de tokens sin dependencias externas."""
    return _count_tokens(text)


def chunk_text(
    text: str,
    *,
    page_numbers: list[int] | None = None,
    section_names: list[str] | None = None,
    chunk_size: int = 500,
    overlap: int = 75,
) -> list[Chunk]:
    """Divide el texto normalizado en chunks por tokens con overlap.

    Args:
        text: Texto ya normalizado por ``normalize_text``.
        page_numbers: Lista paralela de números de página por párrafo
            (separado por ``\n\n``). Si es ``None``, todos los chunks
            reportan ``page_number=None``.
        section_names: Lista paralela de nombres de sección por párrafo.
        chunk_size: Tamaño máximo de cada chunk en tokens.
        overlap: Cantidad de tokens de solapamiento entre chunks consecutivos.

    Returns:
        Lista de ``Chunk`` ordenados por ``index``.
    """
    if not text or not text.strip():
        return []

    # Dividir el texto en párrafos para respetar límites naturales
    paragraphs = re.split(r"\n\n+", text.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    if not paragraphs:
        return []

    # Construir segmentos con metadatos
    segments: list[tuple[str, int | None, str | None, int]] = []
    for i, para in enumerate(paragraphs):
        tokens = _estimate_tokens(para)
        page = page_numbers[i] if page_numbers and i < len(page_numbers) else None
        section = section_names[i] if section_names and i < len(section_names) else None
        segments.append((para, page, section, tokens))

    # Agrupar segmentos en chunks
    chunks: list[Chunk] = []
    current_segments: list[tuple[str, int | None, str | None, int, int]] = []
    current_tokens = 0
    char_offset = 0  # posición de carácter en el texto original

    for _seg_idx, (text_seg, page, section, seg_tokens) in enumerate(segments):
        # Si agregar este segmento excede el chunk, cerrar el chunk actual
        while current_tokens + seg_tokens > chunk_size and current_segments:
            # Emitir chunk
            chunk_content = "\n\n".join(s[0] for s in current_segments)
            chunk_page = current_segments[0][1]
            chunk_section = current_segments[0][2]
            chunk_char_start = current_segments[0][4]
            chunk_char_end = current_segments[-1][4] + len(current_segments[-1][0])
            chunk_token_count = sum(s[3] for s in current_segments)

            content_hash = hashlib.sha256(chunk_content.encode("utf-8")).hexdigest()[:16]

            chunks.append(
                Chunk(
                    index=len(chunks),
                    content=chunk_content,
                    page_number=chunk_page,
                    section=chunk_section,
                    token_count=chunk_token_count,
                    char_start=chunk_char_start,
                    char_end=chunk_char_end,
                    content_hash=content_hash,
                    metadata={
                        "token_count": chunk_token_count,
                        "char_start": chunk_char_start,
                        "char_end": chunk_char_end,
                        "content_hash": content_hash,
                    },
                )
            )

            # Mantener el overlap para el siguiente chunk
            overlap_tokens = 0
            overlap_segments: list[tuple[str, int | None, str | None, int, int]] = []
            for s in reversed(current_segments):
                if overlap_tokens + s[3] > overlap:
                    break
                overlap_tokens += s[3]
                overlap_segments.append(s)
            overlap_segments.reverse()

            current_segments = overlap_segments
            current_tokens = sum(s[3] for s in current_segments)

        seg_char_pos = char_offset
        current_segments.append((text_seg, page, section, seg_tokens, seg_char_pos))
        current_tokens += seg_tokens
        char_offset += len(text_seg) + 2  # +2 por \n\n

    # Emitir el último chunk si tiene contenido
    if current_segments:
        chunk_content = "\n\n".join(s[0] for s in current_segments)
        chunk_page = current_segments[0][1]
        chunk_section = current_segments[0][2]
        chunk_char_start = current_segments[0][4]
        chunk_char_end = current_segments[-1][4] + len(current_segments[-1][0])
        chunk_token_count = sum(s[3] for s in current_segments)

        content_hash = hashlib.sha256(chunk_content.encode("utf-8")).hexdigest()[:16]

        chunks.append(
            Chunk(
                index=len(chunks),
                content=chunk_content,
                page_number=chunk_page,
                section=chunk_section,
                token_count=chunk_token_count,
                char_start=chunk_char_start,
                char_end=chunk_char_end,
                content_hash=content_hash,
                metadata={
                    "token_count": chunk_token_count,
                    "char_start": chunk_char_start,
                    "char_end": chunk_char_end,
                    "content_hash": content_hash,
                },
            )
        )

    logger.info(
        "chunking_completado",
        extra={
            "total_chunks": len(chunks),
            "chunk_size": chunk_size,
            "overlap": overlap,
            "total_tokens": sum(c.token_count for c in chunks),
        },
    )

    return chunks
