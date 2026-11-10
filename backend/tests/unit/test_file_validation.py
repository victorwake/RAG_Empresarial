"""Pruebas unitarias de validación de archivos cargados."""

import hashlib

import pytest
from app.core.exceptions import (
    DomainValidationError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.services.file_validation import get_extension, sanitize_filename, validate_upload

PDF_BYTES = b"%PDF-1.7 contenido simulado"
DOCX_BYTES = b"PK\x03\x04 contenido simulado"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED = ["pdf", "docx", "txt"]


def _validate(
    filename: str | None,
    content: bytes,
    *,
    content_type: str | None = None,
    max_bytes: int = 1024 * 1024,
    allowed: list[str] | None = None,
):
    return validate_upload(
        filename=filename,
        content_type=content_type,
        content=content,
        max_bytes=max_bytes,
        allowed_extensions=allowed or ALLOWED,
    )


def test_valid_pdf_returns_normalized_data() -> None:
    validated = _validate("Informe.pdf", PDF_BYTES, content_type="application/pdf")

    assert validated.extension == "pdf"
    assert validated.mime_type == "application/pdf"
    assert validated.filename == "Informe.pdf"
    assert validated.original_filename == "Informe.pdf"
    assert validated.checksum == hashlib.sha256(PDF_BYTES).hexdigest()


def test_valid_docx_and_txt_are_accepted() -> None:
    docx = _validate("Memoria.docx", DOCX_BYTES, content_type=DOCX_MIME)
    txt = _validate("notas.txt", b"texto plano", content_type="text/plain")

    assert docx.extension == "docx"
    assert txt.extension == "txt"
    assert txt.mime_type == "text/plain"


def test_extension_is_case_insensitive() -> None:
    validated = _validate("INFORME.PDF", PDF_BYTES, content_type="application/pdf")

    assert validated.extension == "pdf"


def test_disallowed_extension_is_rejected() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        _validate("virus.exe", b"MZ contenido", content_type="application/octet-stream")


def test_missing_extension_is_rejected() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        _validate("archivo", b"contenido", content_type="application/octet-stream")


def test_missing_filename_is_rejected() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        _validate(None, b"contenido")


def test_declared_mime_mismatch_is_rejected() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        _validate("informe.pdf", PDF_BYTES, content_type="text/plain")


def test_empty_file_is_rejected() -> None:
    with pytest.raises(DomainValidationError):
        _validate("informe.pdf", b"", content_type="application/pdf")


def test_oversized_file_is_rejected() -> None:
    with pytest.raises(PayloadTooLargeError):
        _validate("informe.pdf", b"x" * 11, content_type="application/pdf", max_bytes=10)


def test_pdf_with_wrong_signature_is_rejected() -> None:
    with pytest.raises(DomainValidationError):
        _validate("informe.pdf", b"esto no es un pdf", content_type="application/pdf")


def test_docx_with_wrong_signature_is_rejected() -> None:
    with pytest.raises(DomainValidationError):
        _validate("memoria.docx", b"esto no es un docx", content_type=DOCX_MIME)


def test_txt_has_no_signature_check() -> None:
    validated = _validate("notas.txt", b"cualquier bytes", content_type="text/plain")

    assert validated.checksum == hashlib.sha256(b"cualquier bytes").hexdigest()


def test_too_long_filename_is_rejected() -> None:
    with pytest.raises(DomainValidationError):
        _validate(f"{'a' * 300}.pdf", PDF_BYTES, content_type="application/pdf")


def test_get_extension() -> None:
    assert get_extension("Archivo.PDF") == "pdf"
    assert get_extension("backup.tar.gz") == "gz"
    assert get_extension("archivo") == ""
    assert get_extension("") == ""


def test_sanitize_filename_preserves_unicode() -> None:
    assert sanitize_filename("Política RRHH.pdf") == "Política RRHH.pdf"


def test_sanitize_filename_strips_path_components() -> None:
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\evil.pdf") == "evil.pdf"
    assert sanitize_filename("/opt/docs/informe.pdf") == "informe.pdf"


def test_sanitize_filename_replaces_unsafe_characters() -> None:
    sanitized = sanitize_filename('in<>:"|?*forme.pdf')

    assert sanitized.endswith(".pdf")
    assert all(character not in '<>:"|?*' for character in sanitized)


def test_sanitize_filename_removes_control_characters() -> None:
    assert sanitize_filename("ev\x00il.pdf") == "ev_il.pdf"


def test_sanitize_filename_trims_edges_and_dots() -> None:
    assert sanitize_filename("  informe.pdf ") == "informe.pdf"
    assert sanitize_filename("...") == "archivo"
    assert sanitize_filename("..") == "archivo"
    assert sanitize_filename("") == "archivo"


def test_sanitize_filename_truncates_keeping_extension() -> None:
    sanitized = sanitize_filename(f"{'a' * 300}.pdf")

    assert len(sanitized) <= 255
    assert sanitized.endswith(".pdf")
