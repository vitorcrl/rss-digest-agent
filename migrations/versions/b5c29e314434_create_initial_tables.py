"""create initial tables

Revision ID: b5c29e314434
Revises:
Create Date: 2026-06-22 22:48:00.767208

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op


revision: str = 'b5c29e314434'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feeds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "articles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("feed_id", UUID(as_uuid=True), sa.ForeignKey("feeds.id"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False, unique=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("published_at", sa.DateTime, nullable=True),
        sa.Column("relevance_score", sa.SmallInteger, nullable=True),
        sa.Column("summary_pt", sa.Text, nullable=True),
        sa.Column("is_relevant", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("processed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_articles_content_hash", "articles", ["content_hash"])

    op.create_table(
        "digest_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_date", sa.Date, nullable=False, unique=True),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "delivered", "failed", name="digeststatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("articles_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("articles_selected", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("delivered_at", sa.DateTime, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("digest_runs")
    op.drop_index("ix_articles_content_hash", "articles")
    op.drop_table("articles")
    op.drop_table("feeds")
    op.execute("DROP TYPE IF EXISTS digeststatus")
