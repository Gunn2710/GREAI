"""Per-student daily limit on Claude requests, and what each request cost.

A "request" is one thing the student asked for (a coach message, a mnemonic,
a graded sentence), however many API calls it took. Tokens are recorded too,
including prompt-cache reads and writes, so the cost per student is visible.
"""
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AIUsage, utcnow


class Meter:
    """Adds up the API calls and tokens of one student request."""

    def __init__(self) -> None:
        self.calls = 0
        self.input_tokens = self.output_tokens = self.cache_read_tokens = self.cache_write_tokens = 0

    def add(self, usage) -> None:
        self.calls += 1
        if usage is None:
            return
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0


# The meter for the request in progress (see ai.ClaudeService._record).
current_meter: ContextVar[Meter | None] = ContextVar("current_meter", default=None)


def _today(db: Session, user_id: str) -> AIUsage | None:
    return db.get(AIUsage, (user_id, utcnow().date()))


def remaining(db: Session, user_id: str) -> int | None:
    """Requests left today, or None when there is no limit."""
    limit = get_settings().ai_daily_limit
    if limit <= 0:
        return None
    row = _today(db, user_id)
    return max(0, limit - (row.requests if row else 0))


def allowed(db: Session, user_id: str) -> bool:
    left = remaining(db, user_id)
    return left is None or left > 0


def require(db: Session, user_id: str) -> None:
    """Refuse a new request once today's limit is used up."""
    if not allowed(db, user_id):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"You've used today's {get_settings().ai_daily_limit} AI requests. They reset at midnight UTC.",
        )


def record(db: Session, user_id: str, meter: Meter) -> None:
    """Count one request (if it reached Claude) and its tokens."""
    if meter.calls == 0:
        return
    row = _today(db, user_id)
    if row is None:
        row = AIUsage(user_id=user_id, day=utcnow().date(), requests=0, input_tokens=0, output_tokens=0,
                      cache_read_tokens=0, cache_write_tokens=0)
        db.add(row)
    row.requests += 1
    row.input_tokens += meter.input_tokens
    row.output_tokens += meter.output_tokens
    row.cache_read_tokens += meter.cache_read_tokens
    row.cache_write_tokens += meter.cache_write_tokens
    db.commit()


@contextmanager
def metered(db: Session, user_id: str, check: bool = True) -> Iterator[Meter]:
    """Run one student request: refuse it past the limit (if `check`), then record what it used."""
    if check:
        require(db, user_id)
    meter = Meter()
    token = current_meter.set(meter)
    try:
        yield meter
    finally:
        current_meter.reset(token)
        record(db, user_id, meter)
