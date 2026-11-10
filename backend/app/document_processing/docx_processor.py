"""Extracción de texto de archivos DOCX con python-docx."""

from collections.abc import Iterator
from io import BytesIO

from docx import Document as open_document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core.exceptions import ProcessingError
from app.document_processing.base import ExtractionResult, ensure_extractable
from app.document_processing.normalizer import normalize_text

DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
CORRUPT_MESSAGE = "El archivo DOCX está corrupto o no puede abrirse."
NO_TEXT_MESSAGE = "El documento DOCX no contiene texto extraíble."


def _iter_blocks(document: DocxDocument) -> Iterator[Paragraph | Table]:
    """Itera párrafos y tablas del cuerpo en el orden real del documento."""
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _table_lines(table: Table) -> list[str]:
    """Convierte cada fila de la tabla en una línea con celdas separadas."""
    lines: list[str] = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        if any(cells):
            lines.append(" | ".join(cells))
    return lines


def _metadata(document: DocxDocument) -> dict[str, str]:
    """Título y autor declarados en las propiedades del documento."""
    properties = document.core_properties
    metadata: dict[str, str] = {}
    for key in ("title", "author"):
        value = str(getattr(properties, key, None) or "").strip()
        if value:
            metadata[key] = value
    return metadata


class DOCXProcessor:
    """Extractor de texto para documentos Word ``.docx``."""

    def supports(self, mime_type: str) -> bool:
        return mime_type == DOCX_MIME_TYPE

    def extract(self, source: bytes) -> ExtractionResult:
        try:
            document = open_document(BytesIO(source))
        except Exception:
            raise ProcessingError(CORRUPT_MESSAGE) from None
        blocks: list[str] = []
        for block in _iter_blocks(document):
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if text:
                    blocks.append(text)
            else:
                blocks.extend(_table_lines(block))
        text = normalize_text("\n".join(blocks))
        ensure_extractable(text, message=NO_TEXT_MESSAGE)
        return ExtractionResult(
            text=text, pages=(), page_count=None, metadata=_metadata(document)
        )
