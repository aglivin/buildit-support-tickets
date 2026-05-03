import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.tickets import _background_enrich
from app.api.tickets import router as tickets_router
from app.db import async_session_maker
from app.models import EnrichmentStatus, Ticket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # Re-enrich tickets that were left pending by a previous process crash.
    # A ticket older than 1 minute that is still pending was likely orphaned.
    await _sweep_pending_tickets()
    yield


async def _sweep_pending_tickets() -> None:
    cutoff = datetime.now(UTC) - timedelta(minutes=1)
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(Ticket.id).where(
                    Ticket.enrichment_status == EnrichmentStatus.pending,
                    Ticket.created_at < cutoff,
                )
            )
            ids = result.scalars().all()

        if ids:
            logger.info("Startup sweep: re-enriching %d pending ticket(s)", len(ids))
            await asyncio.gather(*(_background_enrich(tid) for tid in ids), return_exceptions=True)
    except SQLAlchemyError:
        logger.exception("Startup sweep failed — continuing without it")


app = FastAPI(
    title="BuildIt Support Ticket Triage API",
    version="0.1.0",
    description="Ingest support tickets, enrich with LLM, store, and query.",
    lifespan=lifespan,
)

app.include_router(tickets_router)


@app.get("/healthz", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
