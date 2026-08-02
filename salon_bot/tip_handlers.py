import asyncio
import re
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.callback_answer import CallbackAnswerMiddleware
from asgiref.sync import sync_to_async

from .keyboards import (
    MENU_BUTTON,
    remove_keyboard,
    tip_amount_keyboard,
    tip_custom_keyboard,
    tip_method_keyboard,
    to_menu_keyboard,
)
from .services import TipsError, get_appointment_by_tips_token, pay_tips
from .states import TipStates

tip_router = Router()
tip_router.callback_query.middleware(CallbackAnswerMiddleware())

AMOUNT_PATTERN = re.compile(r"^\d+(\.\d{1,2})?$")
MAX_TIP = 100000


def _parse_amount(text):
    text = text.strip().replace(",", ".")
    if not AMOUNT_PATTERN.fullmatch(text):
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    if amount <= 0 or amount > MAX_TIP:
        return None
    return amount


async def _tips_info(appointment):
    return await sync_to_async(lambda: {
        "master_name": appointment.slot.master.full_name,
        "service_name": appointment.service.name,
        "client_tg": appointment.client.telegram_id,
        "tips": appointment.tips_amount,
        "tips_payment_id": appointment.tips_payment_id,
    })()


async def _tips_text(appointment):
    info = await _tips_info(appointment)
    if info["tips"]:
        return (
            "Чаевые по этой записи уже отправлены.\n"
            f"Сумма: {info['tips']} руб.\n"
            f"Номер транзакции: {info['tips_payment_id']}"
        )
    return (
        "Чаевые мастеру\n\n"
        f"Мастер: {info['master_name']}\n"
        f"Процедура: {info['service_name']}\n\n"
        "Выберите сумму чаевых:"
    )


async def start_tip_flow(message: Message, state: FSMContext, token: str):
    try:
        appointment = await get_appointment_by_tips_token(token)
    except Exception:
        await message.answer(
            "Ссылка недействительна или устарела.",
            reply_markup=to_menu_keyboard(),
        )
        return
    info = await _tips_info(appointment)
    if info["tips"]:
        await message.answer(
            "Чаевые по этой записи уже отправлены. Спасибо!",
            reply_markup=to_menu_keyboard(),
        )
        return
    if info["client_tg"] and info["client_tg"] > 0 and info["client_tg"] != message.from_user.id:
        await message.answer(
            "Эта ссылка предназначена другому клиенту.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await state.update_data(tip_token=token)
    await message.answer(
        await _tips_text(appointment),
        reply_markup=tip_amount_keyboard(),
    )


@tip_router.callback_query(F.data.startswith("tip:amount:"))
async def on_tip_amount(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[2]
    if value == "custom":
        await state.set_state(TipStates.amount)
        await callback.message.edit_text(
            "Введите сумму чаевых числом (например, 350):",
            reply_markup=None,
        )
        return
    amount = _parse_amount(value)
    if amount is None:
        await callback.message.edit_text(
            "Сумма не распознана. Попробуйте ещё раз:",
            reply_markup=tip_amount_keyboard(),
        )
        return
    await callback.message.edit_text(
        f"Сумма чаевых: {amount} руб.\nВыберите способ оплаты:",
        reply_markup=tip_method_keyboard(amount),
    )


@tip_router.message(TipStates.amount)
async def on_tip_custom_amount(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text in ("Отмена", MENU_BUTTON):
        await state.clear()
        await message.answer("Отменено.", reply_markup=remove_keyboard())
        return
    amount = _parse_amount(text)
    if amount is None:
        await message.answer(
            "Сумма должна быть числом больше 0 (например, 350). Попробуйте ещё раз:",
            reply_markup=tip_custom_keyboard(),
        )
        return
    await state.set_state(None)
    await message.answer(
        f"Сумма чаевых: {amount} руб.\nВыберите способ оплаты:",
        reply_markup=tip_method_keyboard(amount),
    )


@tip_router.callback_query(F.data == "tip:back_amount")
async def on_tip_back_amount(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Выберите сумму чаевых:",
        reply_markup=tip_amount_keyboard(),
    )


@tip_router.callback_query(F.data == "tip:cancel")
async def on_tip_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Хорошо, без чаевых. Спасибо, что были у нас!",
        reply_markup=to_menu_keyboard(),
    )


@tip_router.callback_query(F.data.startswith("tip:method:"))
async def on_tip_method(callback: CallbackQuery, state: FSMContext):
    _, _, method, amount_str = callback.data.split(":")
    amount = _parse_amount(amount_str)
    if amount is None:
        await callback.message.edit_text(
            "Сумма не распознана. Попробуйте ещё раз.",
            reply_markup=tip_amount_keyboard(),
        )
        return
    data = await state.get_data()
    token = data.get("tip_token")
    if not token:
        await callback.message.edit_text(
            "Сессия устарела. Запросите новую ссылку на чаевые.",
            reply_markup=to_menu_keyboard(),
        )
        return
    label = "Банковская карта" if method == "card" else "СБП (СБПэй)"
    await callback.message.edit_text(
        f"Обработка платежа…\nСпособ: {label}\nСумма: {amount} руб."
    )
    await asyncio.sleep(2)
    try:
        appointment = await pay_tips(token, amount, method)
    except TipsError as e:
        await state.clear()
        await callback.message.edit_text(
            str(e),
            reply_markup=to_menu_keyboard(),
        )
        return
    except Exception:
        await callback.message.edit_text(
            "Не удалось обработать платёж (имитация). Попробуйте ещё раз.",
            reply_markup=tip_method_keyboard(amount),
        )
        return
    info = await _tips_info(appointment)
    await state.clear()
    await callback.message.edit_text(
        "Чаевые отправлены! (имитация)\n\n"
        f"Мастер: {info['master_name']}\n"
        f"Сумма: {info['tips']} руб.\n"
        f"Способ: {label}\n"
        f"Номер транзакции: {info['tips_payment_id']}\n\n"
        "Спасибо за щедрость!",
        reply_markup=to_menu_keyboard(),
    )
