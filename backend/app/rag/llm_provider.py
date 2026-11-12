"""Interfaz del proveedor de LLM — Protocol para inyección de dependencias."""

from typing import Protocol


class LLMProvider(Protocol):
    """Proveedor de modelo de lenguaje para generación de respuestas RAG."""

    @property
    def model_name(self) -> str:
        """Nombre del modelo usado, ej. 'gemini-2.0-flash'."""
        ...

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        timeout_seconds: int = 30,
    ) -> "LLMResponse":
        """Genera una respuesta dada una instrucción del sistema y un mensaje.

        Args:
            system_prompt: Instrucciones del sistema con reglas y contexto.
            user_message: Pregunta o instrucción del usuario.
            timeout_seconds: Timeout en segundos para la llamada.

        Returns:
            LLMResponse con el texto, tokens y latencia.
        """
        ...


class LLMResponse:
    """Respuesta del proveedor de LLM con métricas."""

    def __init__(
        self,
        *,
        text: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        model: str,
    ) -> None:
        self.text = text
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.latency_ms = latency_ms
        self.model = model
