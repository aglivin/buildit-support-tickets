"""Deduplication: fingerprint computation and duplicate-request handling."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.dedup import compute_fingerprint
from tests.conftest import TICKET_PAYLOAD, build_ticket


# ── Pure unit tests ────────────────────────────────────────────────────────────


def test_fingerprint_is_deterministic():
    fp1 = compute_fingerprint("anna@example.com", "Hello world")
    fp2 = compute_fingerprint("anna@example.com", "Hello world")
    assert fp1 == fp2


def test_fingerprint_normalises_whitespace_and_case():
    fp1 = compute_fingerprint("ANNA@EXAMPLE.COM", "Hello   world\n")
    fp2 = compute_fingerprint("anna@example.com", "Hello world")
    assert fp1 == fp2


def test_fingerprint_differs_by_email():
    fp1 = compute_fingerprint("anna@example.com", "Same body")
    fp2 = compute_fingerprint("bob@example.com", "Same body")
    assert fp1 != fp2


def test_fingerprint_differs_by_body():
    fp1 = compute_fingerprint("anna@example.com", "First message")
    fp2 = compute_fingerprint("anna@example.com", "Second message")
    assert fp1 != fp2


def test_fingerprint_length_is_64():
    fp = compute_fingerprint("a@b.com", "body")
    assert len(fp) == 64


# ── API-level dedup test ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_within_window_returns_existing_ticket_with_200(client, mock_enrich):
    existing = build_ticket()
    existing_id = str(existing.id)

    # Simulate: find_recent_duplicate returns the existing ticket on the second call
    with patch(
        "app.api.tickets.find_recent_duplicate",
        new_callable=AsyncMock,
        return_value=existing,
    ):
        r = await client.post("/tickets", json=TICKET_PAYLOAD)

    assert r.status_code == 200
    assert r.json()["id"] == existing_id
    # enrich_ticket must NOT have been called for a duplicate
    mock_enrich.assert_not_called()
