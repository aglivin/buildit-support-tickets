"""Tests for GET /tickets — list with filters and pagination."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models import EnrichmentStatus, TicketCategory, TicketPriority
from tests.conftest import build_ticket


def _list_session(mock_session, tickets: list, total: int) -> None:
    """Configure mock_session for list_tickets' two execute() calls."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = total

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = tickets

    mock_session.execute = AsyncMock(side_effect=[count_result, rows_result])


@pytest.mark.asyncio
async def test_list_no_filters_returns_response_shape(client, mock_session):
    ticket = build_ticket(
        enrichment_status=EnrichmentStatus.completed,
        category=TicketCategory.billing,
        priority=TicketPriority.high,
    )
    _list_session(mock_session, [ticket], total=1)

    r = await client.get("/tickets")

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(ticket.id)


@pytest.mark.asyncio
async def test_list_empty_db_returns_zero_items(client, mock_session):
    _list_session(mock_session, [], total=0)

    r = await client.get("/tickets")

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []


@pytest.mark.asyncio
async def test_list_category_filter_passes_through(client, mock_session):
    ticket = build_ticket(
        enrichment_status=EnrichmentStatus.completed,
        category=TicketCategory.billing,
    )
    _list_session(mock_session, [ticket], total=1)

    r = await client.get("/tickets?category=billing")

    assert r.status_code == 200
    assert r.json()["items"][0]["category"] == "billing"


@pytest.mark.asyncio
async def test_list_priority_filter_passes_through(client, mock_session):
    ticket = build_ticket(
        enrichment_status=EnrichmentStatus.completed,
        priority=TicketPriority.high,
    )
    _list_session(mock_session, [ticket], total=1)

    r = await client.get("/tickets?priority=high")

    assert r.status_code == 200
    assert r.json()["items"][0]["priority"] == "high"


@pytest.mark.asyncio
async def test_list_pagination_reflected_in_response(client, mock_session):
    _list_session(mock_session, [], total=50)

    r = await client.get("/tickets?limit=5&offset=10")

    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 5
    assert body["offset"] == 10
    assert body["total"] == 50


@pytest.mark.asyncio
async def test_list_invalid_category_returns_422(client, mock_session):
    r = await client.get("/tickets?category=invalid_value")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_since_filter_accepted(client, mock_session):
    _list_session(mock_session, [], total=0)

    r = await client.get("/tickets?since=2024-01-01T00:00:00")

    assert r.status_code == 200
