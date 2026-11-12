"""Proveedor de LLM basado en Google Gemini."""

import asyncio
import logging
import time

import aiohttp

from app.core.config import Settings
from app.rag.llm_provider import LLMResponse

logger = logging.getLogger("app.rag.gemini_llm")


class GeminiLLMError(Exception):
    """Error al llamar a la API de Gemini."""


class GeminiLLMProvider:
    """Proveedor de LLM usando la API de Gemini (aiohttp).

    Soporta timeouts, reintentos con backoff exponencial y validación
    de la respuesta.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout_seconds: int = 30,
        max_retries: int = 2,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._base_url = base_url.rstrip("/")

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiLLMProvider":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY no está configurado.")
        return cls(
            api_key=settings.gemini_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        timeout_seconds: int | None = None,
    ) -> LLMResponse:
        """Genera una respuesta usando Gemini con system instructions."""
        timeout = timeout_seconds or self._timeout_seconds
        url = f"{self._base_url}/{self._model}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": self._api_key}

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_message}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "topK": 40,
                "topP": 0.95,
            },
        }

        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            start = time.monotonic()
            try:
                async with aiohttp.ClientSession() as session, session.post(
                    url,
                    params=params,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        elapsed_ms = int((time.monotonic() - start) * 1000)
                        text = self._extract_text(data)
                        prompt_tokens = self._extract_field(
                            data, "usageMetadata", "promptTokenCount"
                        ) or 0
                        completion_tokens = self._extract_field(
                            data, "usageMetadata", "candidatesTokenCount"
                        ) or 0
                        return LLMResponse(
                            text=text,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            latency_ms=elapsed_ms,
                            model=self._model,
                        )
                    else:
                        body = await resp.text()
                        raise GeminiLLMError(
                            f"Gemini API {resp.status}: {body[:200]}"
                        )
            except (TimeoutError, aiohttp.ClientError) as exc:
                last_error = exc
                logger.warning(
                    "llm_llamada_error",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "error": str(exc),
                    },
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(2**attempt)
            except GeminiLLMError as exc:
                last_error = exc
                logger.warning(
                    "llm_api_error",
                    extra={
                        "attempt": attempt + 1,
                        "error": str(exc),
                    },
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(2**attempt)

        raise GeminiLLMError(
            f"Error tras {self._max_retries + 1} intentos: {last_error}"
        ) from last_error

    @staticmethod
    def _extract_text(data: dict) -> str:
        try:
            return (
                data["candidates"][0]["content"]["parts"][0]["text"]
            )
        except (KeyError, IndexError) as exc:
            raise GeminiLLMError(
                f"Respuesta inesperada de Gemini: {data}"
            ) from exc

    @staticmethod
    def _extract_field(data: dict, *keys) -> int | None:
        obj = data
        for key in keys:
            if isinstance(obj, dict):
                obj = obj.get(key)
            else:
                return None
        return int(obj) if obj is not None else None
