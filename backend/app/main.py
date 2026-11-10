"""Aplicación FastAPI: middleware, routers y manejo global de errores."""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import APP_VERSION
from app.api.router import api_router
from app.api.routes import health
from app.core.config import get_settings
from app.core.context import clear_context, set_request_id
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.services.processing_service import reconcile_orphan_jobs

logger = logging.getLogger("app.request")

DESCRIPTION = (
    "Plataforma empresarial de consulta de documentación corporativa basada en RAG. "
    "Las respuestas se generan exclusivamente a partir de las fuentes recuperadas."
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await reconcile_orphan_jobs()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    register_exception_handlers(app)

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        set_request_id(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={"method": request.method, "path": request.url.path},
            )
            raise
        else:
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return response
        finally:
            clear_context()

    app.include_router(health.router)
    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
