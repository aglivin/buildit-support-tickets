import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Ticket


def compute_fingerprint(email: str, body: str) -> str:
    normalized_body = re.sub(r"\s+", " ", body.strip()).lower()
    combined = f"{email.lower()}\n{normalized_body}"
    return hashlib.sha256(combined.encode()).hexdigest()


async def find_recent_duplicate(session: AsyncSession, fingerprint: str) -> Ticket | None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.dedup_window_minutes)
    result = await session.execute(
        select(Ticket).where(
            Ticket.fingerprint == fingerprint,
            Ticket.created_at >= cutoff,
        )
    )
    return result.scalar_one_or_none()
