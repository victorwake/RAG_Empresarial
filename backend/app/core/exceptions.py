"""Excepciones de dominio y traducción global a Problem Details (RFC 9457)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.context import get_request_id

logger = logging.getLogger(__name__)

ERROR_BASE_URL = "https://smartdocs.ai/errors"


class AppError(Exception):
    """Error de dominio con traducción HTTP controlada."""

    status_code = 500
    error_type = "internal-error"
    title = "Error interno"
    headers: dict[str, str] | None = None

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.title
        super().__init__(self.detail)


class UnauthorizedError(AppError):
    status_code = 401
    error_type = "unauthorized"
    title = "No autorizado"
    headers = {"WWW-Authenticate": "Bearer"}


class ForbiddenError(AppError):
    status_code = 403
    error_type = "forbidden"
    title = "Acceso denegado"


class NotFoundError(AppError):
    status_code = 404
    error_type = "not-found"
    title = "Recurso no encontrado"


class ConflictError(AppError):
    status_code = 409
    error_type = "conflict"
    title = "Conflicto"


class DomainValidationError(AppError):
    status_code = 422
    error_type = "validation"
    title = "Error de validación"


class ProcessingError(AppError):
    status_code = 422
    error_type = "processing"
    title = "Error de procesamiento"


def _problem(
    *,
    request: Request,
    status_code: int,
    error_type: str,
    title: str,
    detail: str,
    errors: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{ERROR_BASE_URL}/{error_type}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
        "request_id": get_request_id(),
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _problem(
            request=request,
            status_code=exc.status_code,
            error_type=exc.error_type,
            title=exc.title,
            detail=exc.detail,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
            errors.append({"field": location, "message": error.get("msg", "Valor inválido.")})
        return _problem(
            request=request,
            status_code=422,
            error_type="validation",
            title="Error de validación",
            detail="Uno o más campos son inválidos.",
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = "Error" if exc.status_code < 500 else "Error interno"
        return _problem(
            request=request,
            status_code=exc.status_code,
            error_type="http-error",
            title=title,
            detail=str(exc.detail),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            extra={"method": request.method, "path": request.url.path},
        )
        return _problem(
            request=request,
            status_code=500,
            error_type="internal-error",
            title="Error interno",
            detail="Ocurrió un error inesperado.",
        )
