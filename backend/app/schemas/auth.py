"""Schemas de autenticación."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    organization_slug: str = Field(min_length=1, max_length=60)
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int
    refresh_token: str
