"""Initial schema — all 7 tables

Revision ID: 0001
Revises:
Create Date: 2026-04-15

Notes:
- Adds hashed_password to users (required for auth, not in data.txt spec)
- VECTOR(384) locked to all-MiniLM-L6-v2; dimension change requires drop+recreate
- audit_logs is append-only by design (no DELETE/UPDATE endpoint exists)
- Indexes on all frequently-filtered columns per Architect review checklist
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure extensions exist (idempotent — safe to re-run)
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # ── documents ──────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("classification", sa.String(50), nullable=False),
        sa.Column("version", sa.String(20), nullable=False, server_default="v1"),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_documents_department", "documents", ["department"])
    op.create_index("ix_documents_uploaded_by", "documents", ["uploaded_by"])

    # ── document_chunks ────────────────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("chunk_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("role_required", sa.String(50), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_chunks_role_required", "document_chunks", ["role_required"])
    # ivfflat index for fast ANN search — requires chunks to be loaded first
    # RAG Engineer should run: CREATE INDEX ON document_chunks
    #   USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    # after ingestion.

    # ── access_policies ────────────────────────────────────────────────────
    op.create_table(
        "access_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("allowed_classification", sa.String(200), nullable=False),
        sa.UniqueConstraint("role", "department", name="uq_policy_role_dept"),
    )
    op.create_index("ix_policies_role", "access_policies", ["role"])
    op.create_index("ix_policies_department", "access_policies", ["department"])

    # ── audit_logs ─────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column(
            "retrieved_doc_ids",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("response_time_ms", sa.Integer, nullable=True),
        sa.Column("access_decision", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_decision", "audit_logs", ["access_decision"])
    op.create_index("ix_audit_created_at", "audit_logs", ["created_at"])

    # ── chat_sessions ──────────────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_name", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_sessions_user_id", "chat_sessions", ["user_id"])

    # ── chat_messages ──────────────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_messages_session_id", "chat_messages", ["session_id"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("audit_logs")
    op.drop_table("access_policies")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("users")
