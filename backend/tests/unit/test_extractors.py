"""Pruebas unitarias de los extractores de texto por formato."""

import os
from io import BytesIO

import pymupdf
import pytest
from app.core.exceptions import ProcessingError
from app.document_processing import DEFAULT_EXTRACTORS, find_extractor, pdf_processor
from app.document_processing.docx_processor import DOCXProcessor
from app.document_processing.pdf_processor import PDFProcessor
from app.document_processing.txt_processor import TXTProcessor
from docx import Document as DocxDocument
from tests.conftest import build_docx_bytes, build_pdf_bytes, build_scanned_pdf_bytes

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_default_extractors_cover_expected_mime_types() -> None:
    extractors = [find_extractor(DEFAULT_EXTRACTORS, mime) for mime in (
        "application/pdf",
        DOCX_MIME,
        "text/plain",
    )]

    assert extractors == list(DEFAULT_EXTRACTORS)


def test_find_extractor_returns_none_for_unknown_mime() -> None:
    assert find_extractor(DEFAULT_EXTRACTORS, "application/x-otro") is None


def test_extractors_support_only_their_mime_type() -> None:
    pdf, docx, txt = DEFAULT_EXTRACTORS

    assert pdf.supports("application/pdf")
    assert docx.supports(DOCX_MIME)
    assert txt.supports("text/plain")
    assert not pdf.supports(DOCX_MIME)
    assert not docx.supports("application/pdf")
    assert not txt.supports("application/pdf")


def test_pdf_extracts_pages_in_order() -> None:
    source = build_pdf_bytes("Primera pagina del informe.", "Segunda pagina del informe.")

    result = PDFProcessor().extract(source)

    assert result.page_count == 2
    assert [page.page_number for page in result.pages] == [1, 2]
    assert "Primera pagina" in result.pages[0].text
    assert "Segunda pagina" in result.pages[1].text
    assert result.text == "\n\n".join(page.text for page in result.pages)
    assert result.warnings == ()


def test_pdf_reads_metadata() -> None:
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "Informe anual de la empresa.")
        document.set_metadata({"title": "Informe 2026", "author": "Ana Ruiz"})
        source = document.tobytes()

    result = PDFProcessor().extract(source)

    assert result.metadata == {"title": "Informe 2026", "author": "Ana Ruiz"}


def test_pdf_corrupt_file_is_rejected() -> None:
    with pytest.raises(ProcessingError, match="corrupto"):
        PDFProcessor().extract(b"%PDF-1.7 archivo corrupto truncado")


def test_pdf_scanned_without_text_is_rejected() -> None:
    with pytest.raises(ProcessingError, match="OCR"):
        PDFProcessor().extract(build_scanned_pdf_bytes())


def test_pdf_password_protected_is_rejected() -> None:
    with pymupdf.open(stream=build_pdf_bytes("Pagina con contenido."), filetype="pdf") as source:
        protected = source.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secreto", owner_pw="secreto"
        )

    with pytest.raises(ProcessingError, match="contraseña"):
        PDFProcessor().extract(protected)


def test_pdf_reports_warning_for_failed_page(monkeypatch) -> None:
    def _failing_page_text(page: pymupdf.Page) -> str:
        if page.number == 0:
            raise ValueError("pagina danada")
        return page.get_text()

    monkeypatch.setattr(pdf_processor, "_page_text", _failing_page_text)
    source = build_pdf_bytes("Primera pagina del informe.", "Segunda pagina del informe.")

    result = PDFProcessor().extract(source)

    assert result.page_count == 2
    assert [page.page_number for page in result.pages] == [2]
    assert result.warnings == ("La página 1 no pudo extraerse y fue omitida.",)
    assert "Segunda pagina" in result.text


def test_pdf_fails_when_all_pages_fail(monkeypatch) -> None:
    def _failing_page_text(page: pymupdf.Page) -> str:
        raise ValueError("pagina danada")

    monkeypatch.setattr(pdf_processor, "_page_text", _failing_page_text)
    source = build_pdf_bytes("Primera pagina del informe.", "Segunda pagina del informe.")

    with pytest.raises(ProcessingError, match="ninguna página"):
        PDFProcessor().extract(source)


def test_docx_extracts_paragraphs_and_tables_in_order() -> None:
    document = DocxDocument()
    document.add_paragraph("Region norte del pais")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Region"
    table.cell(0, 1).text = "Vacancias"
    table.cell(1, 0).text = "Norte"
    table.cell(1, 1).text = "12"
    document.add_paragraph("Cierre del informe anual")
    buffer = BytesIO()
    document.save(buffer)

    result = DOCXProcessor().extract(buffer.getvalue())

    parts = [
        "Region norte del pais",
        "Region | Vacancias",
        "Norte | 12",
        "Cierre del informe anual",
    ]
    positions = [result.text.index(part) for part in parts]
    assert result.page_count is None
    assert result.pages == ()
    assert positions == sorted(positions)


def test_docx_reads_core_properties() -> None:
    source = build_docx_bytes(
        "Parrafo del documento con autor.", title="Memoria 2026", author="Luis Sosa"
    )

    result = DOCXProcessor().extract(source)

    assert result.metadata == {"title": "Memoria 2026", "author": "Luis Sosa"}


def test_docx_corrupt_file_is_rejected() -> None:
    with pytest.raises(ProcessingError, match="corrupto"):
        DOCXProcessor().extract(b"PK\x03\x04 no es un docx real")


def test_docx_without_content_is_rejected() -> None:
    buffer = BytesIO()
    DocxDocument().save(buffer)

    with pytest.raises(ProcessingError, match="no contiene texto"):
        DOCXProcessor().extract(buffer.getvalue())


def test_txt_decodes_utf8() -> None:
    result = TXTProcessor().extract("El café del día está listo".encode())

    assert result.text == "El café del día está listo"


def test_txt_decodes_utf8_with_bom() -> None:
    result = TXTProcessor().extract("Notas de la reunión del equipo".encode("utf-8-sig"))

    assert result.text == "Notas de la reunión del equipo"


def test_txt_decodes_utf16_with_bom() -> None:
    result = TXTProcessor().extract("Acta de la reunión de trabajo".encode("utf-16"))

    assert result.text == "Acta de la reunión de trabajo"


def test_txt_detects_latin1() -> None:
    result = TXTProcessor().extract("El café del día en la oficina".encode("latin-1"))

    assert result.text == "El café del día en la oficina"


def test_txt_rejects_undecodable_bytes() -> None:
    with pytest.raises(ProcessingError, match="decodificar"):
        TXTProcessor().extract(os.urandom(1024))


def test_txt_rejects_whitespace_only_content() -> None:
    with pytest.raises(ProcessingError, match="contenido legible"):
        TXTProcessor().extract(b"   \n\t\n   ")
