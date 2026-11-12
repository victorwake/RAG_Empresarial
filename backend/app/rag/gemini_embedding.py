"""Proveedor de embeddings usando Google Gemini (aiohttp)."""

import asyncio
import logging

import aiohttp

from app.core.config import Settings, get_settings
from app.rag.embedding_provider import EmbeddingError

logger = logging.getLogger("app.embeddings.gemini")

DEFAULT_BATCH_SIZE = 5
MAX_RETRIES = 3
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiEmbeddingProvider:
    """Genera embeddings vía la API de Gemini con lotes y reintentos."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-004",
        dimension: int = 768,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_retries: int = MAX_RETRIES,
        timeout: int = 30,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dimension = dimension
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._timeout = timeout

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "GeminiEmbeddingProvider":
        """Construye el proveedor desde la configuración actual."""
        settings = settings or get_settings()
        return cls(
            api_key=settings.gemini_api_key or "",
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para documentos en lotes."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            embeddings = await self._request_embeddings(batch)
            all_embeddings.extend(embeddings)

        if len(all_embeddings) != len(texts):
            raise EmbeddingError(
                f"Se esperaban {len(texts)} embeddings, se obtuvieron {len(all_embeddings)}."
            )

        return all_embeddings

    async def embed_query(self, text: str) -> list[float]:
        """Genera el embedding de una consulta."""
        embeddings = await self._request_embeddings([text])
        if not embeddings:
            raise EmbeddingError("El proveedor no devolvió embedding para la consulta.")
        return embeddings[0]

    async def _request_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Envía un lote de textos a la API de Gemini con reintentos."""
        payload = {
            "contents": [{"parts": [{"text": t}]} for t in texts],
        }
        url = f"{BASE_URL}/{self._model}:embedContent"
        # Para múltiples textos, usar batchEmbedContents
        if len(texts) > 1:
            payload = {
                "requests": [
                    {"model": f"{BASE_URL}/{self._model}", "content": {"parts": [{"text": t}]}}
                    for t in texts
                ]
            }
            url = f"{BASE_URL}/{self._model}:batchEmbedContents"

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session, session.post(
                    url,
                    params={"key": self._api_key},
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if len(texts) > 1:
                            # batchEmbedContents response
                            embeddings = [
                                r["embedding"]["values"]
                                for r in result.get("embeddings", [])
                            ]
                        else:
                            # embedContent response
                            embeddings = [result["embedding"]["values"]]
                        logger.debug(
                            "embeddings_obtenidos",
                            extra={
                                "model": self._model,
                                "count": len(embeddings),
                                "dimension": len(embeddings[0]) if embeddings else 0,
                            },
                        )
                        return embeddings
                    else:
                        body = await resp.text()
                        raise EmbeddingError(
                            f"API Gemini devolvió HTTP {resp.status}: {body}"
                        )
            except (TimeoutError, aiohttp.ClientError) as exc:
                last_error = exc
                wait = 2**attempt
                logger.warning(
                    "embedding_reintento",
                    extra={
                        "attempt": attempt,
                        "max_retries": self._max_retries,
                        "error": str(exc),
                    },
                )
                await asyncio.sleep(wait)
            except EmbeddingError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(2**attempt)
                else:
                    raise EmbeddingError(f"Error inesperado: {exc}") from exc

        raise EmbeddingError(
            f"El proveedor de embeddings falló después de "
            f"{self._max_retries} intentos: {last_error}"
        ) from last_error
