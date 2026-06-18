"""Точка входу Telegram-бота (aiogram)."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from ..config import settings
from ..database import init_db
from .handlers import admin, user

# Вмикаємо UTF-8 для консолі Windows, щоб коректно виводити емодзі/кирилицю.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("glowcrm.bot")


async def _set_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="💄 Запустити / головне меню"),
        BotCommand(command="menu", description="🏠 Головне меню"),
        BotCommand(command="admin", description="🛠 Адмін-панель (для адмінів)"),
        BotCommand(command="help", description="ℹ️ Допомога"),
    ])


async def run() -> None:
    token = settings.BOT_TOKEN
    if not token or token.startswith("PUT-YOUR"):
        print(
            "\n❌ Не вказано BOT_TOKEN.\n"
            "   1) Скопіюйте .env.example у .env  (Windows: copy .env.example .env)\n"
            "   2) Вставте токен від @BotFather у змінну BOT_TOKEN\n"
            "   3) Вкажіть свій username у ADMIN_USERNAMES\n"
        )
        return

    init_db()

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_routers(user.router, admin.router)

    await _set_commands(bot)
    me = await bot.get_me()
    logger.info("Бот @%s запущено. Адміни: %s", me.username, settings.ADMIN_USERNAMES or "—")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот зупинено.")


if __name__ == "__main__":
    main()
