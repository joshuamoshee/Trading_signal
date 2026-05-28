import asyncio
import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from src.config import settings
from src.data.prices import get_recent_bars
from src.analysis.technicals import generate_signal, TechnicalSignal
from src.db.journal import record_signal, get_recent_signal
from src.analysis.market import build_snapshot
from src.analysis.coach import coach_report
from src.analysis.risk import stop_distance_pips

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("scanner")

# BTC/USD removed. Safely under the API rate limit.
SYMBOLS = ["XAU/USD", "EUR/USD", "GBP/USD"]
SCAN_INTERVAL_SECONDS = 300          
PER_SYMBOL_DELAY_SECONDS = 8         


def format_signal(s: TechnicalSignal) -> str:
    arrow = "🟢" if s.side == "BUY" else "🔴"
    
    # Combine the list of checks into a clean, multi-line string
    checklist_str = "\n".join(s.checklist)
    
    return (
        f"{arrow} <b>{s.side} {s.symbol}</b>\n"
        f"Strength: {s.score}/{s.total_checks} ⚡\n\n"
        f"Entry: <code>{s.entry:.5f}</code>\n"
        f"Stop Loss: <code>{s.stop_loss:.5f}</code>\n"
        f"Take Profit: <code>{s.take_profit:.5f}</code>\n"
        f"RR: <b>{s.rr}:1</b>\n\n"
        f"<b>📊 Confluences:</b>\n"
        f"{checklist_str}\n\n"
        f"<i>⚠️ Setup briefed for manual execution. Please review chart.</i>"
    )


async def scan_once(bot: Bot) -> None:
    for symbol in SYMBOLS:
        try:
            df = get_recent_bars(symbol, interval="5min", outputsize=250)
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

        recent = await get_recent_signal(symbol, within_minutes=60)
        if recent is not None:
            logger.info(
                "Recent signal exists for %s (id=%s, sent %s) — skipping",
                symbol, recent.id, recent.sent_at,
            )
            await asyncio.sleep(PER_SYMBOL_DELAY_SECONDS)
            continue

        try:
            signal_id = await record_signal(
                symbol=signal.symbol, side=signal.side,
                entry=signal.entry, stop_loss=signal.stop_loss,
                take_profit=signal.take_profit, rr=signal.rr,
                reason=signal.reason,
                meta={"strategy": "ema_crossover_v2", "score": signal.score},
            )
        except Exception:
            logger.exception("DB write failed for %s — not sending Telegram", symbol)
            await asyncio.sleep(PER_SYMBOL_DELAY_SECONDS)
            continue

        # ─────────────────────────────────────────────────────────────
        # COACH BLOCK — replaces the old plain send_message try/except
        # ─────────────────────────────────────────────────────────────
        snapshot = build_snapshot(symbol, df, timeframe="5min")
        sl_pips = stop_distance_pips(symbol, float(signal.entry), float(signal.stop_loss))
        setup = {
            "side": signal.side,
            "entry": float(signal.entry),
            "stop_loss": float(signal.stop_loss),
            "take_profit": float(signal.take_profit),
            "rr": float(signal.rr),
            "stop_distance_pips": sl_pips,
            "confluences_passed": signal.score,
        }
        account = {"size_gbp": 50, "risk_per_trade_pct": 2, "max_leverage": 10}

        report = await coach_report(
            snapshot.to_dict() if snapshot else {}, setup, account
        )

        message = report.strip() if report else format_signal(signal)
        message += f"\n\n<i>Signal #{signal_id}</i>"

        try:
            await bot.send_message(
                chat_id=settings.telegram_owner_chat_id,
                text=message[:4000],
            )
            logger.info("SIGNAL #%s sent (coach=%s)", signal_id, bool(report))
        except Exception:
            logger.exception("Telegram send failed for signal id=%s", signal_id)
        # ─────────────────────────────────────────────────────────────

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