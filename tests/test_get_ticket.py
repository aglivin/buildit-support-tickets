"""Tests for GET /tickets/{id}."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models import EnrichmentStatus
from tests.conftest import build_ticket


@pytest.mark.asyncio
async def test_get_existing_ticket_returns_200(client, mock_session):
    ticket = build_ticket(enrichment_status=EnrichmentStatus.completed)

    found = MagicMock()
    found.scalar_one_or_none.return_value = ticket
    mock_session.execute = AsyncMock(return_value=found)

    r = await client.get(f"/tickets/{ticket.id}")

    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(ticket.id)
    assert body["title"] == ticket.title
    assert body["customer_email"] == ticket.customer_email
    assert body["enrichment_status"] == "completed"


@pytest.mark.asyncio
async def test_get_nonexistent_ticket_returns_404(client, mock_session):
    # mock_session.execute already returns scalar_one_or_none=None by default
    unknown_id = uuid.uuid4()

    r = await client.get(f"/tickets/{unknown_id}")

    assert r.status_code == 404
    assert r.json()["detail"] == "Ticket not found"


@pytest.mark.asyncio
async def test_get_invalid_uuid_returns_422(client):
    r = await client.get("/tickets/not-a-uuid")
    assert r.status_code == 422
