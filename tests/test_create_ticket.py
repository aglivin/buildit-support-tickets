"""Happy-path and failure-mode tests for POST /tickets."""
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import ENRICHMENT_RESULT, TICKET_PAYLOAD


@pytest.mark.asyncio
async def test_create_ticket_returns_201_with_enrichment(client, mock_enrich):
    r = await client.post("/tickets", json=TICKET_PAYLOAD)

    assert r.status_code == 201
    body = r.json()
    assert body["enrichment_status"] == "completed"
    assert body["category"] == "billing"
    assert body["priority"] == "high"
    assert body["sentiment"] == "negative"
    assert body["summary"] == ENRICHMENT_RESULT.summary
    assert body["title"] == TICKET_PAYLOAD["title"]
    assert body["customer_email"] == "anna@example.com"
    assert "id" in body


@pytest.mark.asyncio
async def test_create_ticket_llm_failure_returns_201_with_failed_status(client):
    with patch(
        "app.api.tickets.enrich_ticket",
        new_callable=AsyncMock,
        return_value=(None, "api_error:500"),
    ):
        r = await client.post("/tickets", json=TICKET_PAYLOAD)

    assert r.status_code == 201
    body = r.json()
    assert body["enrichment_status"] == "failed"
    assert body["enrichment_error"] == "api_error:500"
    assert body["category"] is None
    assert body["priority"] is None


@pytest.mark.asyncio
async def test_create_ticket_timeout_returns_202(client):
    with patch(
        "app.api.tickets.enrich_ticket",
        new_callable=AsyncMock,
        return_value=(None, "timeout"),
    ), patch("app.api.tickets._background_enrich", new_callable=AsyncMock):
        r = await client.post("/tickets", json=TICKET_PAYLOAD)

    assert r.status_code == 202
    body = r.json()
    assert body["enrichment_status"] == "pending"


@pytest.mark.asyncio
async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_invalid_email_rejected(client, mock_enrich):
    bad = {**TICKET_PAYLOAD, "customer_email": "not-an-email"}
    r = await client.post("/tickets", json=bad)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_empty_body_rejected(client, mock_enrich):
    bad = {**TICKET_PAYLOAD, "body": "   "}
    r = await client.post("/tickets", json=bad)
    assert r.status_code == 422
