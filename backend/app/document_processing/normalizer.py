"""Normalización de texto extraído: saltos, espacios y caracteres de control."""

import re

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\n]+")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")
_HYPHENATED_BREAK = re.compile(r"([a-zà-ÿ])-\n(?=[a-zà-ÿ])")


def normalize_text(text: str) -> str:
    """Normaliza el texto extraído manteniendo la estructura de párrafos.

    Unifica los saltos de línea a ``\n``, elimina caracteres de control,
    convierte los espacios Unicode a espacio simple, colapsa espacios
    repetidos, recorta los extremos de cada línea, colapsa más de dos líneas
    vacías consecutivas y une cortes de palabra con guion cuando la línea
    siguiente comienza en minúscula.
    """
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    sanitized = _CONTROL_CHARACTERS.sub(" ", unified)
    rejoined = _HYPHENATED_BREAK.sub(r"\1", sanitized)
    collapsed = _HORIZONTAL_WHITESPACE.sub(" ", rejoined)
    lines = [line.strip() for line in collapsed.split("\n")]
    without_excess = _EXCESS_BLANK_LINES.sub("\n\n", "\n".join(lines))
    return without_excess.strip()
