import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from src.config import settings

logging.basicConfig(level=logging.INFO)

bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Welcome to Signal Bot.\n\n"
        "Commands:\n"
        "/subscribe — get live signals\n"
        "/status — see today's performance"
    )

@dp.message(Command("status"))
async def cmd_status(message: Message) -> None:
    await message.answer("📊 No signals yet today.")

async def main() -> None:
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())