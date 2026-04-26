from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models import EnrichmentStatus, TicketCategory, TicketPriority, TicketSentiment


class TicketCreate(BaseModel):
    title: str
    body: str
    customer_email: str

    @field_validator("customer_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        parts = v.split("@")
        if len(parts) != 2 or "." not in parts[1]:
            raise ValueError("Invalid email address")
        return v

    @field_validator("title", "body")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be empty")
        return v


class EnrichmentResult(BaseModel):
    category: TicketCategory
    priority: TicketPriority
    sentiment: TicketSentiment
    summary: str


class TicketRead(BaseModel):
    id: UUID
    title: str
    body: str
    customer_email: str
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    sentiment: TicketSentiment | None = None
    summary: str | None = None
    enrichment_status: EnrichmentStatus
    enrichment_error: str | None = None
    enriched_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    items: list[TicketRead]
    total: int
    limit: int
    offset: int
