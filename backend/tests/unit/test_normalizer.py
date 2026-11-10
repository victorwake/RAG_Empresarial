"""Pruebas unitarias de la normalización de texto extraído."""

from app.document_processing.normalizer import normalize_text


def test_unifies_line_endings() -> None:
    unified = normalize_text("linea uno\r\nlinea dos\rlinea tres")

    assert unified == "linea uno\nlinea dos\nlinea tres"


def test_removes_control_characters() -> None:
    assert normalize_text("a\x00b\x07c\x0bd") == "a b c d"


def test_collapses_horizontal_whitespace() -> None:
    assert normalize_text("hola\t\tmundo   final") == "hola mundo final"


def test_collapses_non_breaking_space() -> None:
    assert normalize_text("palabra\u00a0unida") == "palabra unida"


def test_strips_each_line() -> None:
    assert normalize_text("  hola  \n  mundo  ") == "hola\nmundo"


def test_collapses_excess_blank_lines() -> None:
    assert normalize_text("uno\n\n\n\n\ndos") == "uno\n\ndos"


def test_preserves_paragraph_break() -> None:
    assert normalize_text("uno\n\ndos") == "uno\n\ndos"


def test_joins_hyphenated_word_break() -> None:
    assert normalize_text("impor-\ntante") == "importante"


def test_joins_hyphenated_break_with_accents() -> None:
    assert normalize_text("capí-\ntulo") == "capítulo"


def test_keeps_hyphen_before_uppercase() -> None:
    assert normalize_text("ejem-\nPLO") == "ejem-\nPLO"


def test_only_whitespace_becomes_empty() -> None:
    assert normalize_text("   \n\t\n  ") == ""


def test_preserves_unicode_text() -> None:
    assert normalize_text("política y gestión del conocimiento") == (
        "política y gestión del conocimiento"
    )
