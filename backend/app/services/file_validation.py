"""Validación de archivos cargados: extensión, MIME, firma, nombre y checksum."""

import hashlib
import os
import re
from dataclasses import dataclass

from app.core.exceptions import (
    DomainValidationError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)

ALLOWED_MIME_BY_EXTENSION: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}

MAX_FILENAME_LENGTH = 255

_UNSAFE_CHARACTERS = set('<>:"/\\|?*')


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    """Resultado de validar un archivo cargado."""

    extension: str
    mime_type: str
    filename: str
    original_filename: str
    content: bytes
    checksum: str


def get_extension(filename: str) -> str:
    """Devuelve la extensión en minúsculas, sin punto."""
    return os.path.splitext(filename)[1].lower().lstrip(".")


def sanitize_filename(name: str, *, max_length: int = MAX_FILENAME_LENGTH) -> str:
    """Sanea un nombre de archivo para almacenamiento y despliegue.

    Elimina separadores de ruta, caracteres de control y caracteres problemáticos;
    conserva Unicode válido y la extensión. Nunca devuelve una cadena vacía.
    """
    basename = name.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(
        "_" if character in _UNSAFE_CHARACTERS or not character.isprintable() else character
        for character in basename
    )
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip(" .")
    if not cleaned:
        cleaned = "archivo"
    if len(cleaned) > max_length:
        stem, extension = os.path.splitext(cleaned)
        if extension and len(extension) < max_length:
            cleaned = stem[: max_length - len(extension)] + extension
        else:
            cleaned = cleaned[:max_length]
    return cleaned


def validate_upload(
    *,
    filename: str | None,
    content_type: str | None,
    content: bytes,
    max_bytes: int,
    allowed_extensions: list[str],
) -> ValidatedUpload:
    """Valida un archivo y devuelve sus datos normalizados.

    Rechaza extensiones y MIME no permitidos (``415``), archivos vacíos o cuya
    firma no coincida con la extensión (``422``) y archivos demasiado grandes
    (``413``). El checksum SHA-256 se calcula sobre el contenido completo.
    """
    original_name = (filename or "").strip()
    if not original_name:
        raise UnsupportedMediaTypeError("El archivo no tiene nombre.")

    extension = get_extension(original_name)
    if not extension or extension not in allowed_extensions:
        raise UnsupportedMediaTypeError(
            f"La extensión .{extension or 'desconocida'} no está permitida."
        )

    mime_type = ALLOWED_MIME_BY_EXTENSION.get(extension)
    if mime_type is None:
        raise UnsupportedMediaTypeError(f"La extensión .{extension} no está permitida.")

    declared_type = (content_type or "").split(";", 1)[0].strip().lower()
    if declared_type and declared_type != mime_type:
        raise UnsupportedMediaTypeError(
            "El tipo MIME declarado no coincide con la extensión del archivo."
        )

    if len(content) > max_bytes:
        raise PayloadTooLargeError("El archivo supera el límite de tamaño permitido.")
    if not content:
        raise DomainValidationError("El archivo está vacío.")

    _validate_signature(extension, content)

    return ValidatedUpload(
        extension=extension,
        mime_type=mime_type,
        filename=sanitize_filename(original_name),
        original_filename=_clean_original_name(original_name),
        content=content,
        checksum=hashlib.sha256(content).hexdigest(),
    )


def _validate_signature(extension: str, content: bytes) -> None:
    if extension == "pdf" and not content.startswith(b"%PDF-"):
        raise DomainValidationError(
            "El contenido del archivo no corresponde a un PDF válido."
        )
    if extension == "docx" and not content.startswith(b"PK"):
        raise DomainValidationError(
            "El contenido del archivo no corresponde a un DOCX válido."
        )


def _clean_original_name(name: str) -> str:
    cleaned = "".join(character if character.isprintable() else " " for character in name)
    if len(cleaned) > MAX_FILENAME_LENGTH:
        raise DomainValidationError("El nombre del archivo supera los 255 caracteres.")
    return cleaned
