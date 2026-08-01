import asyncio
import logging
import os

import django
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from salon_bot.handlers import router  # noqa: E402
from salon_bot.master_handlers import master_router  # noqa: E402
from salon_bot.phone_handlers import phone_router  # noqa: E402
from salon_bot.procedure_handlers import procedure_router  # noqa: E402
from salon_bot.salon_handlers import salon_router  # noqa: E402
from salon_bot.shared_handlers import shared_router  # noqa: E402
from salon_bot.staff_handlers import staff_router  # noqa: E402


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("BOT_TOKEN not found in .env")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    dp.include_router(salon_router)
    dp.include_router(master_router)
    dp.include_router(procedure_router)
    dp.include_router(phone_router)
    dp.include_router(staff_router)
    dp.include_router(shared_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
