"""init

Revision ID: 0001
Revises:
Create Date: 2026-04-26 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ticket_category = postgresql.ENUM(
        "billing",
        "bug",
        "feature_request",
        "account",
        "other",
        name="ticket_category",
    )
    ticket_priority = postgresql.ENUM(
        "low",
        "medium",
        "high",
        "urgent",
        name="ticket_priority",
    )
    ticket_sentiment = postgresql.ENUM(
        "negative",
        "neutral",
        "positive",
        name="ticket_sentiment",
    )
    enrichment_status = postgresql.ENUM(
        "pending",
        "completed",
        "failed",
        name="enrichment_status",
    )

    ticket_category.create(op.get_bind(), checkfirst=True)
    ticket_priority.create(op.get_bind(), checkfirst=True)
    ticket_sentiment.create(op.get_bind(), checkfirst=True)
    enrichment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("customer_email", sa.String(320), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM(
                "billing",
                "bug",
                "feature_request",
                "account",
                "other",
                name="ticket_category",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "low", "medium", "high", "urgent", name="ticket_priority", create_type=False
            ),
            nullable=True,
        ),
        sa.Column(
            "sentiment",
            postgresql.ENUM(
                "negative", "neutral", "positive", name="ticket_sentiment", create_type=False
            ),
            nullable=True,
        ),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column(
            "enrichment_status",
            postgresql.ENUM(
                "pending", "completed", "failed", name="enrichment_status", create_type=False
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("enrichment_error", sa.Text, nullable=True),
        sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_unique_constraint("uq_tickets_fingerprint", "tickets", ["fingerprint"])
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"])
    op.create_index("ix_tickets_category_created", "tickets", ["category", "created_at"])
    op.create_index("ix_tickets_priority_created", "tickets", ["priority", "created_at"])
    op.create_index("ix_tickets_email", "tickets", ["customer_email"])


def downgrade() -> None:
    op.drop_table("tickets")
    op.execute("DROP TYPE IF EXISTS ticket_category")
    op.execute("DROP TYPE IF EXISTS ticket_priority")
    op.execute("DROP TYPE IF EXISTS ticket_sentiment")
    op.execute("DROP TYPE IF EXISTS enrichment_status")
