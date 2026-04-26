import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TicketCategory(str, enum.Enum):
    billing = "billing"
    bug = "bug"
    feature_request = "feature_request"
    account = "account"
    other = "other"


class TicketPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class TicketSentiment(str, enum.Enum):
    negative = "negative"
    neutral = "neutral"
    positive = "positive"


class EnrichmentStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    customer_email: Mapped[str] = mapped_column(String(320), nullable=False)
    # sha256 hex of (email_lower + normalized_body); globally unique — see dedup service
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    category: Mapped[TicketCategory | None] = mapped_column(
        SAEnum(TicketCategory, name="ticket_category"), nullable=True
    )
    priority: Mapped[TicketPriority | None] = mapped_column(
        SAEnum(TicketPriority, name="ticket_priority"), nullable=True
    )
    sentiment: Mapped[TicketSentiment | None] = mapped_column(
        SAEnum(TicketSentiment, name="ticket_sentiment"), nullable=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_status: Mapped[EnrichmentStatus] = mapped_column(
        SAEnum(EnrichmentStatus, name="enrichment_status"),
        nullable=False,
        default=EnrichmentStatus.pending,
    )
    enrichment_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_tickets_created_at", "created_at"),
        Index("ix_tickets_category_created", "category", "created_at"),
        Index("ix_tickets_priority_created", "priority", "created_at"),
        Index("ix_tickets_email", "customer_email"),
    )
