"""Unit tests for app/services/enrichment.py."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIError, APIStatusError

from app.models import TicketCategory, TicketPriority, TicketSentiment
from app.schemas import EnrichmentResult
from app.services.enrichment import _call_llm, enrich_ticket

VALID_ARGS = json.dumps(
    {
        "category": "billing",
        "priority": "high",
        "sentiment": "negative",
        "summary": "Customer was charged twice and requests a refund.",
    }
)

_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def _tool_call(args: str = VALID_ARGS) -> MagicMock:
    tc = MagicMock()
    tc.function.name = "record_triage"
    tc.function.arguments = args
    return tc


def _response(tool_calls: list | None = None) -> MagicMock:
    msg = MagicMock()
    msg.tool_calls = tool_calls if tool_calls is not None else []
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _mock_client(
    response: MagicMock | None = None,
    side_effect: BaseException | None = None,
) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=response,
        side_effect=side_effect,
    )
    return client


# ── _call_llm tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_llm_success_returns_enrichment_result():
    mock = _mock_client(response=_response([_tool_call()]))
    with patch("app.services.enrichment.get_client", return_value=mock):
        result, error = await _call_llm("Charged twice", "I see two charges")

    assert error is None
    assert isinstance(result, EnrichmentResult)
    assert result.category == TicketCategory.billing
    assert result.priority == TicketPriority.high
    assert result.sentiment == TicketSentiment.negative


@pytest.mark.asyncio
async def test_call_llm_api_status_error_returns_error_code():
    resp = httpx.Response(429, request=_REQUEST)
    exc = APIStatusError("Rate limited", response=resp, body=None)
    mock = _mock_client(side_effect=exc)
    with patch("app.services.enrichment.get_client", return_value=mock):
        result, error = await _call_llm("title", "body")

    assert result is None
    assert error == "api_error:429"


@pytest.mark.asyncio
async def test_call_llm_api_error_returns_unexpected_error():
    exc = APIError("Connection error", request=_REQUEST, body=None)
    mock = _mock_client(side_effect=exc)
    with patch("app.services.enrichment.get_client", return_value=mock):
        result, error = await _call_llm("title", "body")

    assert result is None
    assert error == "unexpected_error"


@pytest.mark.asyncio
async def test_call_llm_no_tool_call_returns_no_tool_use():
    mock = _mock_client(response=_response(tool_calls=[]))
    with patch("app.services.enrichment.get_client", return_value=mock):
        result, error = await _call_llm("title", "body")

    assert result is None
    assert error == "no_tool_use"


@pytest.mark.asyncio
async def test_call_llm_invalid_json_returns_invalid_tool_input():
    mock = _mock_client(response=_response([_tool_call("not valid json{{")]))
    with patch("app.services.enrichment.get_client", return_value=mock):
        result, error = await _call_llm("title", "body")

    assert result is None
    assert error == "invalid_tool_input"


@pytest.mark.asyncio
async def test_call_llm_wrong_enum_value_returns_invalid_tool_input():
    bad_args = json.dumps(
        {
            "category": "unknown_category",
            "priority": "high",
            "sentiment": "negative",
            "summary": "test",
        }
    )
    mock = _mock_client(response=_response([_tool_call(bad_args)]))
    with patch("app.services.enrichment.get_client", return_value=mock):
        result, error = await _call_llm("title", "body")

    assert result is None
    assert error == "invalid_tool_input"


# ── enrich_ticket wrapper tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_ticket_timeout_returns_timeout():
    with patch(
        "app.services.enrichment._call_llm",
        new_callable=AsyncMock,
        side_effect=TimeoutError(),
    ):
        result, error = await enrich_ticket("title", "body")

    assert result is None
    assert error == "timeout"


@pytest.mark.asyncio
async def test_enrich_ticket_success_passes_through():
    expected = EnrichmentResult(
        category=TicketCategory.billing,
        priority=TicketPriority.high,
        sentiment=TicketSentiment.negative,
        summary="Customer charged twice.",
    )
    with patch(
        "app.services.enrichment._call_llm",
        new_callable=AsyncMock,
        return_value=(expected, None),
    ):
        result, error = await enrich_ticket("title", "body")

    assert error is None
    assert result == expected
