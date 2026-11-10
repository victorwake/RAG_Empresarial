"""Contrato común de los extractores de texto de la Etapa 4."""

from dataclasses import dataclass, field
from typing import Protocol

from app.core.exceptions import ProcessingError

MIN_EXTRACTABLE_CHARS = 10
NO_TEXT_MESSAGE = "El documento no contiene texto extraíble."


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    """Texto normalizado de una página concreta del documento."""

    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Resultado de la extracción de texto de un documento.

    ``text`` es el contenido completo normalizado; ``pages`` preserva el texto
    por página cuando el formato lo permite; ``page_count`` es ``None`` para
    formatos sin paginación; ``metadata`` incluye título y autor cuando el
    archivo los declara; ``warnings`` registra problemas no fatales por página.
    """

    text: str
    pages: tuple[ExtractedPage, ...]
    page_count: int | None
    metadata: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


class TextExtractor(Protocol):
    """Extractor de texto para un tipo MIME concreto."""

    def supports(self, mime_type: str) -> bool: ...

    def extract(self, source: bytes) -> ExtractionResult: ...


def ensure_extractable(text: str, *, message: str = NO_TEXT_MESSAGE) -> None:
    """Falla cuando el texto extraído no tiene contenido útil (§ rag-pipeline 3.3)."""
    if len(text.strip()) < MIN_EXTRACTABLE_CHARS:
        raise ProcessingError(message)
