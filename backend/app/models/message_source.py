"""Modelo de fuente citada en un mensaje del asistente."""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import REAL
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MessageSource(Base):
    __tablename__ = "message_sources"
    __table_args__ = (
        UniqueConstraint(
            "message_id", "chunk_id", name="uq_message_sources_message_id_chunk_id"
        ),
        CheckConstraint("rank > 0", name="ck_message_sources_rank_positive"),
        Index("ix_message_sources_message_id", "message_id"),
        Index("ix_message_sources_chunk_id", "chunk_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[float] = mapped_column(REAL, nullable=False)

    def __repr__(self) -> str:
        return (
            f"MessageSource(id={self.id!r}, message_id={self.message_id!r}, "
            f"chunk_id={self.chunk_id!r}, rank={self.rank!r})"
        )
