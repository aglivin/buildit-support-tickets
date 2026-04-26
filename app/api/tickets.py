import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker, get_session
from app.models import EnrichmentStatus, Ticket, TicketCategory, TicketPriority
from app.schemas import TicketCreate, TicketListResponse, TicketRead
from app.services.dedup import compute_fingerprint, find_recent_duplicate
from app.services.enrichment import enrich_ticket

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tickets", tags=["tickets"])


async def _background_enrich(ticket_id: UUID) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket or ticket.enrichment_status == EnrichmentStatus.completed:
            return

        enrichment, error = await enrich_ticket(ticket.title, ticket.body)

        if enrichment:
            ticket.category = enrichment.category
            ticket.priority = enrichment.priority
            ticket.sentiment = enrichment.sentiment
            ticket.summary = enrichment.summary
            ticket.enrichment_status = EnrichmentStatus.completed
            ticket.enriched_at = datetime.now(timezone.utc)
            ticket.enrichment_error = None
        else:
            ticket.enrichment_status = EnrichmentStatus.failed
            ticket.enrichment_error = error

        await session.commit()
        logger.info(
            "Background enrichment finished ticket_id=%s status=%s",
            ticket_id,
            ticket.enrichment_status,
        )


@router.post("", response_model=TicketRead)
async def create_ticket(
    payload: TicketCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> Ticket:
    email = payload.customer_email  # already lowercased by validator
    fingerprint = compute_fingerprint(email, payload.body)

    # Fast path: duplicate within window → return existing ticket (idempotent)
    existing = await find_recent_duplicate(session, fingerprint)
    if existing:
        response.status_code = 200
        return existing

    ticket = Ticket(
        title=payload.title,
        body=payload.body,
        customer_email=email,
        fingerprint=fingerprint,
        enrichment_status=EnrichmentStatus.pending,
    )
    session.add(ticket)
    try:
        await session.commit()
        await session.refresh(ticket)
    except IntegrityError:
        # Race condition: concurrent request already inserted this fingerprint
        await session.rollback()
        dup = await session.execute(select(Ticket).where(Ticket.fingerprint == fingerprint))
        ticket = dup.scalar_one()
        response.status_code = 200
        return ticket

    # Attempt synchronous enrichment within the configured timeout budget
    enrichment, error = await enrich_ticket(ticket.title, ticket.body)

    if enrichment:
        ticket.category = enrichment.category
        ticket.priority = enrichment.priority
        ticket.sentiment = enrichment.sentiment
        ticket.summary = enrichment.summary
        ticket.enrichment_status = EnrichmentStatus.completed
        ticket.enriched_at = datetime.now(timezone.utc)
        ticket.enrichment_error = None
        await session.commit()
        await session.refresh(ticket)
        response.status_code = 201
    elif error == "timeout":
        # LLM slow: return immediately, finish enrichment after response
        ticket.enrichment_status = EnrichmentStatus.pending
        ticket.enrichment_error = error
        await session.commit()
        await session.refresh(ticket)
        background_tasks.add_task(_background_enrich, ticket.id)
        response.status_code = 202
    else:
        ticket.enrichment_status = EnrichmentStatus.failed
        ticket.enrichment_error = error
        await session.commit()
        await session.refresh(ticket)
        response.status_code = 201

    return ticket


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    category: Optional[TicketCategory] = Query(None),
    priority: Optional[TicketPriority] = Query(None),
    since: Optional[datetime] = Query(None, description="ISO-8601 datetime, e.g. 2024-01-01"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> TicketListResponse:
    q = select(Ticket)
    count_q = select(func.count()).select_from(Ticket)

    if category is not None:
        q = q.where(Ticket.category == category)
        count_q = count_q.where(Ticket.category == category)
    if priority is not None:
        q = q.where(Ticket.priority == priority)
        count_q = count_q.where(Ticket.priority == priority)
    if since is not None:
        q = q.where(Ticket.created_at >= since)
        count_q = count_q.where(Ticket.created_at >= since)

    total = (await session.execute(count_q)).scalar_one()
    rows = (
        await session.execute(
            q.order_by(Ticket.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    return TicketListResponse(items=list(rows), total=total, limit=limit, offset=offset)


@router.get("/{ticket_id}", response_model=TicketRead)
async def get_ticket(
    ticket_id: UUID, session: AsyncSession = Depends(get_session)
) -> Ticket:
    result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket
