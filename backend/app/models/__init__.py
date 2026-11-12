"""Registro central de modelos para que Alembic los descubra."""

from app.models.conversation import Conversation
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import (
    DocumentStatus,
    JobStatus,
    JobType,
    MessageRole,
    MessageStatus,
    UserRole,
)
from app.models.message import Message
from app.models.message_source import MessageSource
from app.models.organization import Organization
from app.models.processing_job import ProcessingJob
from app.models.refresh_token import RefreshToken
from app.models.user import User

__all__ = [
    "Conversation",
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "JobStatus",
    "JobType",
    "Message",
    "MessageRole",
    "MessageSource",
    "MessageStatus",
    "Organization",
    "ProcessingJob",
    "RefreshToken",
    "User",
    "UserRole",
]
