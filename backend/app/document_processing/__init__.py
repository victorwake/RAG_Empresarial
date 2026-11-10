"""Extractores de texto por formato y selección por tipo MIME."""

from collections.abc import Iterable

from app.document_processing.base import (
    ExtractedPage,
    ExtractionResult,
    TextExtractor,
    ensure_extractable,
)
from app.document_processing.docx_processor import DOCXProcessor
from app.document_processing.pdf_processor import PDFProcessor
from app.document_processing.txt_processor import TXTProcessor

DEFAULT_EXTRACTORS: tuple[TextExtractor, ...] = (
    PDFProcessor(),
    DOCXProcessor(),
    TXTProcessor(),
)


def find_extractor(
    extractors: Iterable[TextExtractor], mime_type: str
) -> TextExtractor | None:
    """Devuelve el primer extractor que soporta el tipo MIME dado."""
    for extractor in extractors:
        if extractor.supports(mime_type):
            return extractor
    return None


__all__ = [
    "DEFAULT_EXTRACTORS",
    "DOCXProcessor",
    "ExtractedPage",
    "ExtractionResult",
    "PDFProcessor",
    "TXTProcessor",
    "TextExtractor",
    "ensure_extractable",
    "find_extractor",
]
