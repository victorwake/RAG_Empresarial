"""Extracción de texto plano con detección de codificación."""

import codecs

from charset_normalizer import from_bytes

from app.core.exceptions import ProcessingError
from app.document_processing.base import ExtractionResult, ensure_extractable
from app.document_processing.normalizer import normalize_text

TXT_MIME_TYPE = "text/plain"
UNDECODABLE_MESSAGE = "No se pudo decodificar el archivo de texto."
NO_TEXT_MESSAGE = "El archivo de texto no contiene contenido legible."

_BOM_ENCODINGS: list[tuple[bytes, str]] = [
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
    (codecs.BOM_UTF8, "utf-8-sig"),
]


def _decode(source: bytes) -> str:
    """Decodifica el contenido respetando BOM y detectando la codificación."""
    for bom, encoding in _BOM_ENCODINGS:
        if source.startswith(bom):
            return source.decode(encoding)
    try:
        return source.decode("utf-8")
    except UnicodeDecodeError:
        pass
    match = from_bytes(source).best()
    if match is None:
        raise ProcessingError(UNDECODABLE_MESSAGE)
    return str(match)


class TXTProcessor:
    """Extractor de texto para ``text/plain``."""

    def supports(self, mime_type: str) -> bool:
        return mime_type == TXT_MIME_TYPE

    def extract(self, source: bytes) -> ExtractionResult:
        text = normalize_text(_decode(source))
        ensure_extractable(text, message=NO_TEXT_MESSAGE)
        return ExtractionResult(text=text, pages=(), page_count=None)
