import asyncio
import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from src.data.prices import get_current_price
from src.db.journal import get_open_signals, resolve_signal

logger = logging.getLogger("watcher")

CHECK_INTERVAL_SECONDS = 60       # how often to check open signals
EXPIRY_HOURS = 24                 # auto-expire signals older than this
PER_SYMBOL_DELAY_SECONDS = 8      # respect Twelve Data rate limit


def _evaluate(side: str, price: Decimal, sl: Decimal, tp: Decimal) -> str | None:
    """Return 'WON', 'LOST', or None (still open) for the current price."""
    if side == "BUY":
        if price >= tp:
            return "WON"
        if price <= sl:
            return "LOST"
    else:  # SELL
        if price <= tp:
            return "WON"
        if price >= sl:
            return "LOST"
    return None


async def check_open_signals() -> None:
    signals = await get_open_signals()
    if not signals:
        logger.info("No open signals to check")
        return

    logger.info("Checking %d open signal(s)", len(signals))

    # Group by symbol so we fetch each price only once
    symbols = {s.symbol for s in signals}
    prices: dict[str, Decimal] = {}
    for symbol in symbols:
        p = get_current_price(symbol)
        if p is not None:
            prices[symbol] = Decimal(str(p))
        await asyncio.sleep(PER_SYMBOL_DELAY_SECONDS)

    now = datetime.now(timezone.utc)
    for sig in signals:
        price = prices.get(sig.symbol)
        if price is None:
            logger.warning("No price for %s, skipping signal #%s", sig.symbol, sig.id)
            continue

        outcome = _evaluate(
            sig.side, price, Decimal(str(sig.stop_loss)), Decimal(str(sig.take_profit))
        )

        if outcome is not None:
            await resolve_signal(signal_id=sig.id, status=outcome, exit_price=price)
        elif now - sig.sent_at > timedelta(hours=EXPIRY_HOURS):
            await resolve_signal(signal_id=sig.id, status="EXPIRED", exit_price=price)
        else:
            logger.info(
                "Signal #%s still open: %s price=%s sl=%s tp=%s",
                sig.id, sig.symbol, price, sig.stop_loss, sig.take_profit,
            )


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    logger.info("Watcher started. interval=%ds", CHECK_INTERVAL_SECONDS)
    while True:
        try:
            await check_open_signals()
        except Exception:
            logger.exception("Watcher iteration failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Watcher stopped by user")