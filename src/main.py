import asyncio
import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from src.config import settings
from src.data.prices import get_recent_bars
from src.analysis.technicals import generate_signal, TechnicalSignal
from src.db.journal import record_signal, get_recent_signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("scanner")

SYMBOLS = ["EUR/USD", "GBP/USD", "BTC/USD"]
SCAN_INTERVAL_SECONDS = 300          # 5 minutes
PER_SYMBOL_DELAY_SECONDS = 8         # stay under Twelve Data's 8 req/min free tier



def format_signal(s: TechnicalSignal) -> str:
    arrow = "🟢" if s.side == "BUY" else "🔴"
    return (
        f"{arrow} <b>{s.side} {s.symbol}</b>\n\n"
        f"Entry: <code>{s.entry:.5f}</code>\n"
        f"Stop Loss: <code>{s.stop_loss:.5f}</code>\n"
        f"Take Profit: <code>{s.take_profit:.5f}</code>\n"
        f"RR: <b>{s.rr}:1</b>\n\n"
        f"<i>{s.reason}</i>\n\n"
        f"⚠️ Educational only — not financial advice. Manage your own risk."
    )


async def scan_once(bot: Bot) -> None:
    for symbol in SYMBOLS:
        try:
            df = get_recent_bars(symbol, interval="5min", outputsize=100)
        except Exception:
            logger.exception("Fetch failed for %s", symbol)
            await asyncio.sleep(PER_SYMBOL_DELAY_SECONDS)
            continue

        if df.empty:
            logger.warning("Empty data for %s — skipping", symbol)
            await asyncio.sleep(PER_SYMBOL_DELAY_SECONDS)
            continue

        signal = generate_signal(symbol, df)
        if signal is None:
            logger.info("No signal for %s (close=%s)", symbol, df["close"].iloc[-1])
            await asyncio.sleep(PER_SYMBOL_DELAY_SECONDS)
            continue

        # DB-backed dedup: skip if we already fired for this symbol in the last hour
        recent = await get_recent_signal(symbol, within_minutes=60)
        if recent is not None:
            logger.info(
                "Recent signal exists for %s (id=%s, sent %s) — skipping",
                symbol, recent.id, recent.sent_at,
            )
            await asyncio.sleep(PER_SYMBOL_DELAY_SECONDS)
            continue

        # Persist FIRST. If the DB write fails, we don't Telegram a phantom.
        try:
            signal_id = await record_signal(
                symbol=signal.symbol, side=signal.side,
                entry=signal.entry, stop_loss=signal.stop_loss,
                take_profit=signal.take_profit, rr=signal.rr,
                reason=signal.reason,
                meta={"strategy": "ema_crossover_v1"},
            )
        except Exception:
            logger.exception("DB write failed for %s — not sending Telegram", symbol)
            await asyncio.sleep(PER_SYMBOL_DELAY_SECONDS)
            continue

        # Then notify
        try:
            await bot.send_message(
                chat_id=settings.telegram_owner_chat_id,
                text=format_signal(signal) + f"\n\n<i>Signal #{signal_id}</i>",
            )
            logger.info("SIGNAL #%s sent to Telegram", signal_id)
        except Exception:
            logger.exception("Telegram send failed for signal id=%s", signal_id)

        await asyncio.sleep(PER_SYMBOL_DELAY_SECONDS)


async def main() -> None:
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info(
        "Scanner started. symbols=%s interval=%ds",
        SYMBOLS, SCAN_INTERVAL_SECONDS,
    )
    try:
        while True:
            try:
                await scan_once(bot)
            except Exception:
                logger.exception("Scan iteration failed")
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")