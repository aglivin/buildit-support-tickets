import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_session
from app.main import app
from app.models import EnrichmentStatus, Ticket, TicketCategory, TicketPriority, TicketSentiment
from app.schemas import EnrichmentResult

TICKET_PAYLOAD = {
    "title": "Charged twice for October subscription",
    "body": "I see two charges of €49 on my card from Oct 3. Please refund one.",
    "customer_email": "anna@example.com",
}

ENRICHMENT_RESULT = EnrichmentResult(
    category=TicketCategory.billing,
    priority=TicketPriority.high,
    sentiment=TicketSentiment.negative,
    summary="Customer was charged twice and requests a refund.",
)


def build_ticket(**overrides) -> Ticket:
    """Return an in-memory Ticket with all required fields set."""
    now = datetime.now(timezone.utc)
    t = Ticket(
        title=TICKET_PAYLOAD["title"],
        body=TICKET_PAYLOAD["body"],
        customer_email="anna@example.com",
        fingerprint="a" * 64,
        enrichment_status=EnrichmentStatus.pending,
    )
    t.id = uuid.uuid4()
    t.created_at = now
    t.updated_at = now
    for k, v in overrides.items():
        setattr(t, k, v)
    return t


@pytest.fixture()
def mock_enrich():
    """Patch enrich_ticket to return a successful EnrichmentResult."""
    with patch(
        "app.api.tickets.enrich_ticket",
        new_callable=AsyncMock,
        return_value=(ENRICHMENT_RESULT, None),
    ) as m:
        yield m


@pytest.fixture()
def mock_session():
    """AsyncMock session that simulates a fresh DB with no existing tickets."""
    session = AsyncMock()

    no_result = MagicMock()
    no_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=no_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def _refresh(obj):
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)
    return session


@pytest.fixture()
async def client(mock_session):
    """AsyncClient wired to the FastAPI app with the DB session mocked out."""

    async def _override():
        yield mock_session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
