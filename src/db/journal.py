import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import func, select
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
    
async def get_open_signals() -> list[Signal]:
    """All signals still awaiting an outcome."""
    async with SessionFactory() as s:
        result = await s.execute(
            select(Signal).where(Signal.status == "OPEN").order_by(Signal.sent_at)
        )
        return list(result.scalars().all())


async def resolve_signal(
    *,
    signal_id: int,
    status: str,             # "WON", "LOST", or "EXPIRED"
    exit_price: Optional[Decimal],
) -> None:
    """Write the outcome of a signal back to the DB. Idempotent."""
    async with SessionFactory() as s, s.begin():
        signal = await s.get(Signal, signal_id)
        if signal is None or signal.status != "OPEN":
            return  # already resolved or gone
        signal.status = status
        signal.exit_price = exit_price
        signal.resolved_at = datetime.now(timezone.utc)
        logger.info(
            "Signal #%s resolved: %s exit=%s", signal_id, status, exit_price
        )

async def get_performance_stats() -> dict:
    """Aggregate win/loss stats across all signals."""
    async with SessionFactory() as s:
        result = await s.execute(
            select(
                func.count().label("total"),
                func.count().filter(Signal.status == "WON").label("wins"),
                func.count().filter(Signal.status == "LOST").label("losses"),
                func.count().filter(Signal.status == "OPEN").label("open_count"),
                func.count().filter(Signal.status == "EXPIRED").label("expired"),
                func.coalesce(
                    func.sum(Signal.rr).filter(Signal.status == "WON"), 0
                ).label("r_won"),
            )
        )
        row = result.one()

        wins, losses = row.wins, row.losses
        resolved = wins + losses
        win_rate = (wins / resolved * 100) if resolved else 0.0
        # A win earns +rr R (reward = rr × risk); a loss costs -1R.
        total_r = float(row.r_won) - losses
        expectancy = (total_r / resolved) if resolved else 0.0

        return {
            "total": row.total,
            "wins": wins,
            "losses": losses,
            "open": row.open_count,
            "expired": row.expired,
            "win_rate": win_rate,
            "total_r": total_r,
            "expectancy": expectancy,
        }