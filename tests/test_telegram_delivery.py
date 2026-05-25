import asyncio
from decimal import Decimal

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from src.config import settings
from src.analysis.technicals import TechnicalSignal
from src.main import format_signal


async def _send():
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        fake = TechnicalSignal(
            symbol="EUR/USD", side="BUY",
            entry=Decimal("1.08500"),
            stop_loss=Decimal("1.08350"),
            take_profit=Decimal("1.08800"),
            rr=Decimal("2.0"),
            reason="TEST signal — pipeline verification",
        )
        await bot.send_message(
            chat_id=settings.telegram_owner_chat_id,
            text=format_signal(fake),
        )
    finally:
        await bot.session.close()


def test_send_fake_signal():
    asyncio.run(_send())