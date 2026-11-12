"""Tabla document_chunks y índice HNSW para búsqueda vectorial.

Revision ID: 0004_document_chunks_y_pgvector
Revises: 0003_documents_y_processing_jobs
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_document_chunks_y_pgvector"
down_revision: str | None = "0003_documents_y_processing_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Obtener la dimensión desde la configuración
    from app.core.config import get_settings
    dim = get_settings().embedding_dimension

    op.create_table(
        "document_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "embedding",
            sa.Text,  # vector(N) — se altera después para el tipo correcto
            nullable=False,
        ),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_chunks"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_document_chunks_organization_id_id"
        ),
        sa.UniqueConstraint(
            "document_id", "chunk_index",
            name="uq_document_chunks_document_id_chunk_index",
        ),
        sa.CheckConstraint(
            "chunk_index >= 0", name="ck_document_chunks_chunk_index_non_neg"
        ),
        sa.CheckConstraint(
            "length(content) > 0", name="ck_document_chunks_content_not_empty"
        ),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number > 0",
            name="ck_document_chunks_page_number_positive",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_document_chunks_organization_id_document_id_documents",
            ondelete="CASCADE",
        ),
    )

    # Alterar la columna para usar el tipo vector(N) de pgvector
    op.execute(
        f"ALTER TABLE document_chunks ALTER COLUMN embedding "
        f"TYPE vector({dim}) USING embedding::vector({dim})"
    )

    op.create_index(
        "ix_document_chunks_document_id", "document_chunks", ["document_id"]
    )
    op.create_index(
        "ix_document_chunks_organization_id", "document_chunks", ["organization_id"]
    )
    op.create_index(
        "ix_document_chunks_organization_id_document_id",
        "document_chunks",
        ["organization_id", "document_id"],
    )

    # Índice HNSW para búsqueda por similitud coseno
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("document_chunks")
