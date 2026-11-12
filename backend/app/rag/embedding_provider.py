"""Interfaz de proveedor de embeddings y excepciones asociadas."""

from typing import Protocol


class EmbeddingError(Exception):
    """Error al generar embeddings desde el proveedor externo."""


class EmbeddingProvider(Protocol):
    """Proveedor de vectores de embedding para texto.

    Cada implementación debe ser segura para uso concurrente y manejar
    reintentos y timeouts internamente.
    """

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para una lista de textos.

        Args:
            texts: Textos a convertir en vectores.

        Returns:
            Lista de vectores, uno por texto, en el mismo orden.

        Raises:
            EmbeddingError: Si el proveedor falla tras los reintentos.
        """
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Genera el embedding de una consulta.

        Algunos proveedores usan instrucciones distintas para documentos
        y consultas; este método permite esa diferenciación.

        Args:
            text: Texto de la consulta.

        Returns:
            Vector de embedding.

        Raises:
            EmbeddingError: Si el proveedor falla tras los reintentos.
        """
        ...

    @property
    def model_name(self) -> str:
        """Nombre del modelo de embeddings (ej. ``text-embedding-004``)."""
        ...

    @property
    def dimension(self) -> int:
        """Dimensión del vector producido por este proveedor."""
        ...
