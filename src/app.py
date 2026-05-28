import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message

from src.config import settings
from src.main import scan_once, SCAN_INTERVAL_SECONDS
from src.watcher import check_open_signals, CHECK_INTERVAL_SECONDS
from src.db.journal import get_performance_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("app")

dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Signal Bot is live.\n\n"
        "/stats — performance so far\n"
        "/ping — check the bot is alive\n\n"
        "⚠️ Educational only — not financial advice."
    )


@dp.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    await message.answer("pong ✅")


@dp.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    stats = await get_performance_stats()
    if stats["total"] == 0:
        await message.answer("No signals recorded yet.")
        return

    resolved = stats["wins"] + stats["losses"]
    text = (
        f"📊 <b>Performance</b>\n\n"
        f"Total signals: {stats['total']}\n"
        f"✅ Wins: {stats['wins']}\n"
        f"❌ Losses: {stats['losses']}\n"
        f"⏳ Open: {stats['open']}\n"
        f"⌛ Expired: {stats['expired']}\n\n"
        f"Win rate: <b>{stats['win_rate']:.1f}%</b> ({stats['wins']}/{resolved} resolved)\n"
        f"Total: <b>{stats['total_r']:+.1f}R</b>\n"
        f"Expectancy: <b>{stats['expectancy']:+.2f}R</b> per trade"
    )
    await message.answer(text)


async def scanner_loop(bot: Bot) -> None:
    logger.info("Scanner loop started")
    while True:
        try:
            await scan_once(bot)
        except Exception:
            logger.exception("Scanner iteration failed")
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


async def watcher_loop() -> None:
    logger.info("Watcher loop started")
    while True:
        try:
            await check_open_signals()
        except Exception:
            logger.exception("Watcher iteration failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def main() -> None:
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("Starting bot + scanner + watcher concurrently")
    try:
        await asyncio.gather(
            dp.start_polling(bot),
            scanner_loop(bot),
            watcher_loop(),
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")