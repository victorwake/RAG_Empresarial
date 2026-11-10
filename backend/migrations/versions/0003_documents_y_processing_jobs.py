"""Tablas documents y processing_jobs.

Revision ID: 0003_documents_y_processing_jobs
Revises: 0002_users_y_refresh_tokens
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_documents_y_processing_jobs"
down_revision: str | None = "0002_users_y_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

document_status = postgresql.ENUM("PENDING", "PROCESSING", "COMPLETED", "FAILED",
                                  name="document_status")
job_status = postgresql.ENUM("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="job_status")
job_type = postgresql.ENUM("INGEST", "REPROCESS", name="job_type")


def upgrade() -> None:
    document_status.create(op.get_bind(), checkfirst=True)
    job_status.create(op.get_bind(), checkfirst=True)
    job_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "PROCESSING", "COMPLETED", "FAILED",
                name="document_status", create_type=False,
            ),
            server_default=sa.text("'PENDING'::document_status"),
            nullable=False,
        ),
        sa.Column("checksum", sa.CHAR(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_documents_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "uploaded_by"],
            ["users.organization_id", "users.id"],
            name="fk_documents_organization_id_uploaded_by_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint("organization_id", "id", name="uq_documents_organization_id_id"),
        sa.UniqueConstraint(
            "organization_id", "checksum", name="uq_documents_organization_id_checksum"
        ),
        sa.CheckConstraint("file_size > 0", name="ck_documents_file_size_positive"),
    )
    op.create_index(
        "ix_documents_organization_id_status",
        "documents",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_documents_organization_id_created_at",
        "documents",
        ["organization_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_documents_uploaded_by",
        "documents",
        ["uploaded_by"],
        unique=False,
    )

    op.create_table(
        "processing_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "job_type",
            postgresql.ENUM("INGEST", "REPROCESS", name="job_type", create_type=False),
            server_default=sa.text("'INGEST'::job_type"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "PROCESSING", "COMPLETED", "FAILED",
                name="job_status", create_type=False,
            ),
            server_default=sa.text("'PENDING'::job_status"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_processing_jobs_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_processing_jobs_organization_id_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_processing_jobs"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_processing_jobs_organization_id_id"
        ),
    )
    op.create_index(
        "ix_processing_jobs_document_id_created_at",
        "processing_jobs",
        ["document_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_processing_jobs_status",
        "processing_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_processing_jobs_organization_id_created_at",
        "processing_jobs",
        ["organization_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "uq_processing_jobs_active",
        "processing_jobs",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'PROCESSING')"),
    )


def downgrade() -> None:
    op.drop_index("uq_processing_jobs_active", table_name="processing_jobs")
    op.drop_index(
        "ix_processing_jobs_organization_id_created_at", table_name="processing_jobs"
    )
    op.drop_index("ix_processing_jobs_status", table_name="processing_jobs")
    op.drop_index(
        "ix_processing_jobs_document_id_created_at", table_name="processing_jobs"
    )
    op.drop_table("processing_jobs")
    op.drop_index("ix_documents_uploaded_by", table_name="documents")
    op.drop_index("ix_documents_organization_id_created_at", table_name="documents")
    op.drop_index("ix_documents_organization_id_status", table_name="documents")
    op.drop_table("documents")
    job_type.drop(op.get_bind(), checkfirst=True)
    job_status.drop(op.get_bind(), checkfirst=True)
    document_status.drop(op.get_bind(), checkfirst=True)
