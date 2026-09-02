import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from django.conf import settings
from django.core.management.base import BaseCommand

from salon_bot.handlers import router
from salon_bot.master_handlers import master_router
from salon_bot.payment_handlers import payment_router
from salon_bot.phone_handlers import phone_router
from salon_bot.procedure_handlers import procedure_router
from salon_bot.review_handlers import review_router
from salon_bot.salon_handlers import salon_router
from salon_bot.shared_handlers import shared_router
from salon_bot.staff_handlers import staff_router
from salon_bot.tip_handlers import tip_router


class Command(BaseCommand):
    help = "Запускает Telegram-бота записи в салон"

    def handle(self, *args, **options):
        try:
            asyncio.run(self.run_bot())
        except KeyboardInterrupt:
            pass

    async def run_bot(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            handlers=[
                logging.FileHandler("bot.log", encoding="utf-8"),
                logging.StreamHandler(),
            ],
        )
        if not settings.BOT_TOKEN:
            raise SystemExit("BOT_TOKEN not found in .env")

        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher()
        dp.include_router(router)
        dp.include_router(salon_router)
        dp.include_router(master_router)
        dp.include_router(procedure_router)
        dp.include_router(phone_router)
        dp.include_router(staff_router)
        dp.include_router(payment_router)
        dp.include_router(review_router)
        dp.include_router(tip_router)
        dp.include_router(shared_router)

        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)