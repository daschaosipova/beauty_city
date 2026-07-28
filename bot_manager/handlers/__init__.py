import os
from aiogram import Router 

def get_client_router() -> Router:
    from .start import start_router
    from .booking import booking_router 

    # Переносим создание роутера и include внутрь функции (добавляем 4 пробела)
    main_router = Router()
    main_router.include_router(start_router)
    main_router.include_router(booking_router)

    return main_router