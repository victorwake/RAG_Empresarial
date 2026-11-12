"""Router agregado de la API v1."""

from fastapi import APIRouter

from app.api.routes import auth, documents, search

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)
