import os
import django
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import asyncio
import logging
from aiogram import Bot, Dispatcher
from bot_manager import tg_bot
from bot_manager.handlers import get_client_router
from bot_manager.handlers.payment_handler import payment_router


ORGANIZER_ID = int(os.getenv("ORGANIZER_ID"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Включаем логирование, чтобы видеть ошибки в консоли
logging.basicConfig(level=logging.INFO)

async def main():
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Подключаем модули (роутеры) всех разработчиков
    dp.include_router(get_client_router())
    dp.include_router(payment_router)

    print("🚀 Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())