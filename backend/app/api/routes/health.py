"""Health check con verificación de base de datos."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import APP_VERSION
from app.api.dependencies import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_db)) -> JSONResponse:
    database_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_ok = False

    payload = {
        "status": "ok" if database_ok else "degraded",
        "version": APP_VERSION,
        "database": "ok" if database_ok else "unavailable",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return JSONResponse(status_code=200 if database_ok else 503, content=payload)
