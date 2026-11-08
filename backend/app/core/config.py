"""Configuración de la aplicación basada en variables de entorno."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Configuración validada al arrancar. Si falta algo obligatorio, no inicia."""

    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "SmartDocs AI"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"

    database_url: str
    database_test_url: str | None = None

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    password_min_length: int = 12

    file_storage_root: str = "./data/uploads"
    max_upload_mb: int = 25
    allowed_extensions: str = "pdf,docx,txt"

    embedding_provider: str = "gemini"
    embedding_model: str = "text-embedding-004"
    embedding_dimension: int = 768
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.0-flash"
    gemini_api_key: str | None = None

    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 75
    retrieval_top_k: int = 6
    retrieval_min_score: float = 0.35
    retrieval_max_context_tokens: int = 6000
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2
    prompt_version: str = "v1"

    @model_validator(mode="after")
    def _validate_security_settings(self) -> "Settings":
        if self.app_env != "test" and len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET debe tener al menos 32 caracteres.")
        if self.password_min_length < 12:
            raise ValueError("PASSWORD_MIN_LENGTH no puede ser menor que 12.")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",") if ext.strip()]


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada. Los tests pueden limpiar la caché."""
    return Settings()
