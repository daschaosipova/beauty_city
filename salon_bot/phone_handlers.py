from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

from .keyboards import (
    phone_back_keyboard,
    phone_salons_keyboard,
    to_menu_keyboard,
)
from .services import get_salon, get_salons

phone_router = Router()
phone_router.callback_query.middleware(CallbackAnswerMiddleware())


@phone_router.callback_query(F.data == "flow:phone")
async def on_flow_phone(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    salons = await get_salons()
    if not salons:
        await callback.message.edit_text(
            "Пока нет доступных салонов. Попробуйте позже.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await callback.message.edit_text(
        "Выберите салон, чтобы посмотреть контакты:",
        reply_markup=phone_salons_keyboard(salons),
    )


@phone_router.callback_query(F.data.startswith("phone:salon:"))
async def on_phone_salon(callback: CallbackQuery, state: FSMContext):
    salon_id = int(callback.data.split(":")[2])
    salon = await get_salon(salon_id)
    await callback.message.edit_text(
        f"Салон: {salon.name}\n"
        f"Адрес: {salon.address}\n"
        f"Телефон: {salon.phone}\n\n"
        "Позвоните нам — оформим запись!",
        reply_markup=phone_back_keyboard(),
    )


@phone_router.callback_query(F.data == "phone:list")
async def on_phone_list(callback: CallbackQuery, state: FSMContext):
    salons = await get_salons()
    if not salons:
        await callback.message.edit_text(
            "Пока нет доступных салонов. Попробуйте позже.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await callback.message.edit_text(
        "Выберите салон, чтобы посмотреть контакты:",
        reply_markup=phone_salons_keyboard(salons),
    )
