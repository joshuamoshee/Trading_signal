import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select
from src.db.models import Signal
from src.db.session import SessionFactory

logger = logging.getLogger(__name__)


async def record_signal(
    *,
    symbol: str,
    side: str,
    entry: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal,
    rr: Decimal,
    reason: str,
    meta: Optional[dict] = None,
) -> int:
    """Persist a signal. Returns the new row's id."""
    async with SessionFactory() as s, s.begin():
        signal = Signal(
            symbol=symbol, side=side,
            entry=entry, stop_loss=stop_loss, take_profit=take_profit,
            rr=rr, reason=reason, status="OPEN", meta=meta or {},
        )
        s.add(signal)
        await s.flush()
        logger.info(
            "Signal persisted id=%s %s %s entry=%s",
            signal.id, side, symbol, entry,
        )
        return signal.id


async def get_recent_signal(symbol: str, within_minutes: int = 60) -> Optional[Signal]:
    """Most recent signal for a symbol within the window. Used for dedup."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
    async with SessionFactory() as s:
        result = await s.execute(
            select(Signal)
            .where(Signal.symbol == symbol, Signal.sent_at >= cutoff)
            .order_by(Signal.sent_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()