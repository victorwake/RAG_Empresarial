"""Tablas conversations, messages y message_sources para el Motor RAG.

Revision ID: 0005_conversations_y_mensajes
Revises: 0004_document_chunks_y_pgvector
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_conversations_y_mensajes"
down_revision: str | None = "0004_document_chunks_y_pgvector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tipos enumerados
    op.execute("CREATE TYPE message_role AS ENUM ('USER', 'ASSISTANT')")
    op.execute(
        "CREATE TYPE message_status AS ENUM ('ANSWERED', 'NO_INFO', 'ERROR')"
    )

    # Tabla conversations
    op.create_table(
        "conversations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=200),
            nullable=False,
            server_default=sa.text("'Nueva conversación'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_conversations_organization_id_id"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["users.organization_id", "users.id"],
            name="fk_conversations_organization_id_user_id_users",
            ondelete="CASCADE",
        ),
    )

    op.execute(
        "CREATE INDEX ix_conversations_organization_id_user_id_created_at "
        "ON conversations (organization_id, user_id, created_at DESC)"
    )
    op.create_index(
        "ix_conversations_user_id", "conversations", ["user_id"]
    )

    # Tabla messages
    op.create_table(
        "messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role", sa.String(length=20), nullable=False
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.CheckConstraint(
            "prompt_tokens >= 0", name="ck_messages_prompt_tokens_non_neg"
        ),
        sa.CheckConstraint(
            "completion_tokens >= 0",
            name="ck_messages_completion_tokens_non_neg",
        ),
        sa.CheckConstraint(
            "latency_ms >= 0", name="ck_messages_latency_ms_non_neg"
        ),
    )

    op.create_index(
        "ix_messages_conversation_id_created_at",
        "messages",
        ["conversation_id", "created_at"],
    )

    # Tabla message_sources
    op.create_table(
        "message_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("relevance_score", sa.REAL, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_message_sources"),
        sa.UniqueConstraint(
            "message_id", "chunk_id",
            name="uq_message_sources_message_id_chunk_id",
        ),
        sa.CheckConstraint("rank > 0", name="ck_message_sources_rank_positive"),
    )

    op.create_index(
        "ix_message_sources_message_id", "message_sources", ["message_id"]
    )
    op.create_index(
        "ix_message_sources_chunk_id", "message_sources", ["chunk_id"]
    )


def downgrade() -> None:
    op.drop_table("message_sources")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.execute("DROP TYPE message_status")
    op.execute("DROP TYPE message_role")
