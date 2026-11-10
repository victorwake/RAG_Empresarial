"""Extracción de texto de archivos PDF con PyMuPDF."""

import pymupdf

from app.core.exceptions import ProcessingError
from app.document_processing.base import (
    ExtractedPage,
    ExtractionResult,
    ensure_extractable,
)
from app.document_processing.normalizer import normalize_text

PDF_MIME_TYPE = "application/pdf"
CORRUPT_MESSAGE = "El archivo PDF está corrupto o no puede abrirse."
PROTECTED_MESSAGE = "El archivo PDF está protegido con contraseña."
NO_TEXT_MESSAGE = "El PDF no contiene texto extraíble; puede requerir OCR."
UNREADABLE_MESSAGE = "No se pudo extraer texto de ninguna página del PDF."


def _page_text(page: pymupdf.Page) -> str:
    """Texto crudo de una página; puede fallar si la página está dañada."""
    return page.get_text()


def _metadata(document: pymupdf.Document) -> dict[str, str]:
    """Título y autor declarados en el PDF, cuando existen."""
    metadata: dict[str, str] = {}
    for key in ("title", "author"):
        value = str(document.metadata.get(key) or "").strip()
        if value:
            metadata[key] = value
    return metadata


class PDFProcessor:
    """Extractor de texto para documentos ``application/pdf``."""

    def supports(self, mime_type: str) -> bool:
        return mime_type == PDF_MIME_TYPE

    def extract(self, source: bytes) -> ExtractionResult:
        try:
            document = pymupdf.open(stream=source, filetype="pdf")
        except Exception:
            raise ProcessingError(CORRUPT_MESSAGE) from None
        try:
            if document.needs_pass:
                raise ProcessingError(PROTECTED_MESSAGE)
            return self._extract_pages(document)
        finally:
            document.close()

    def _extract_pages(self, document: pymupdf.Document) -> ExtractionResult:
        pages: list[ExtractedPage] = []
        warnings: list[str] = []
        for index in range(document.page_count):
            number = index + 1
            try:
                raw_text = _page_text(document.load_page(index))
            except Exception:
                warnings.append(f"La página {number} no pudo extraerse y fue omitida.")
                continue
            normalized = normalize_text(raw_text)
            if normalized:
                pages.append(ExtractedPage(page_number=number, text=normalized))
        if not pages:
            if warnings:
                raise ProcessingError(UNREADABLE_MESSAGE)
            raise ProcessingError(NO_TEXT_MESSAGE)
        text = "\n\n".join(page.text for page in pages)
        ensure_extractable(text, message=NO_TEXT_MESSAGE)
        return ExtractionResult(
            text=text,
            pages=tuple(pages),
            page_count=document.page_count,
            metadata=_metadata(document),
            warnings=tuple(warnings),
        )
