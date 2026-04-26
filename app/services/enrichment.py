import asyncio
import json
import logging

from openai import APIError, APIStatusError

from app.llm.client import get_client
from app.llm.prompts import SYSTEM_PROMPT, TRIAGE_TOOL
from app.schemas import EnrichmentResult
from app.services.pii import mask_for_llm
from app.config import settings

logger = logging.getLogger(__name__)


async def _call_llm(title: str, body: str) -> tuple[EnrichmentResult | None, str | None]:
    masked_title = mask_for_llm(title)
    masked_body = mask_for_llm(body)

    user_content = f"Title: {masked_title}\n\nBody: {masked_body}"

    client = get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=300,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            tools=[TRIAGE_TOOL],
            tool_choice={"type": "function", "function": {"name": "record_triage"}},
        )
    except APIStatusError as exc:
        logger.error("OpenAI API error status=%s", exc.status_code)
        return None, f"api_error:{exc.status_code}"
    except APIError as exc:
        logger.error("OpenAI API error type=%s", type(exc).__name__)
        return None, "unexpected_error"
    except Exception as exc:
        logger.error("Unexpected LLM error type=%s", type(exc).__name__)
        return None, "unexpected_error"

    tool_calls = response.choices[0].message.tool_calls if response.choices else None
    tool_call = next(
        (tc for tc in (tool_calls or []) if tc.function.name == "record_triage"), None
    )
    if not tool_call:
        logger.warning("No tool_call in LLM response")
        return None, "no_tool_use"

    try:
        result = EnrichmentResult.model_validate(json.loads(tool_call.function.arguments))
        return result, None
    except Exception:
        logger.warning("Invalid tool_call arguments: %s", tool_call.function.arguments)
        return None, "invalid_tool_input"


async def enrich_ticket(title: str, body: str) -> tuple[EnrichmentResult | None, str | None]:
    try:
        return await asyncio.wait_for(
            _call_llm(title, body), timeout=settings.llm_timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.warning("LLM enrichment timed out after %.1fs", settings.llm_timeout_seconds)
        return None, "timeout"
