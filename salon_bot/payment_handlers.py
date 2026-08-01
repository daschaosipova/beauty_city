import asyncio

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.callback_answer import CallbackAnswerMiddleware
from asgiref.sync import sync_to_async

from .keyboards import (
    MENU_BUTTON,
    payment_method_keyboard,
    promo_input_keyboard,
    remove_keyboard,
    to_menu_keyboard,
)
from .services import (
    AlreadyPaidError,
    PromoCodeError,
    apply_promo_code,
    clear_promo_code,
    get_appointment,
    pay_appointment,
)
from .states import PromoStates

payment_router = Router()
payment_router.callback_query.middleware(CallbackAnswerMiddleware())

PAYMENT_METHOD_LABELS = {
    "card": "Банковская карта",
    "sbp": "СБП (СБПэй)",
}


async def _safe_edit(awaitable):
    try:
        await awaitable
    except TelegramBadRequest as e:
        if "message is not modified" not in e.message:
            raise


async def _try_delete_prompt(bot: Bot, data):
    prompt_id = data.get("prompt_message_id")
    if not prompt_id:
        return
    try:
        await bot.delete_message(chat_id=data["chat_id"], message_id=prompt_id)
    except Exception:
        pass


def _price_blocks(appointment):
    price = appointment.service.price
    discount = appointment.discount_amount or 0
    final = appointment.final_price or price
    blocks = [f"К оплате: {final} руб."]
    if discount:
        code = appointment.promo_code.code if appointment.promo_code else "промокод"
        percent = appointment.promo_code.discount_percent if appointment.promo_code else 0
        blocks = [
            f"Промокод {code} применён! Скидка −{discount} руб. (−{percent}%)",
            f"К оплате: {final} руб.",
        ]
    return blocks, discount > 0


def _payment_text(appointment):
    if appointment.status == "paid":
        return (
            f"Запись №{appointment.id} уже оплачена.\n"
            f"Сумма: {appointment.final_price or appointment.service.price} руб.\n"
            f"Номер транзакции: {appointment.payment_id}"
        )
    blocks, _ = _price_blocks(appointment)
    return (
        "Онлайн-оплата (имитация)\n\n"
        f"Запись №{appointment.id}\n"
        f"Процедура: {appointment.service.name}\n"
        f"Салон: {appointment.slot.salon.name}\n"
        f"{appointment.slot.date.strftime('%d.%m.%Y')} "
        f"в {appointment.slot.time.strftime('%H:%M')}\n"
        + "\n".join(blocks)
        + "\n\nВыберите способ оплаты:"
    )


def _payment_markup(appointment, appointment_id):
    if appointment.status == "paid":
        return to_menu_keyboard()
    _, has_promo = _price_blocks(appointment)
    return payment_method_keyboard(appointment_id, has_promo)


async def _payment_screen(callback: CallbackQuery, appointment_id: int):
    try:
        appointment = await get_appointment(appointment_id)
    except Exception:
        await _safe_edit(
            callback.message.edit_text(
                "Запись не найдена.",
                reply_markup=to_menu_keyboard(),
            )
        )
        return
    await _safe_edit(
        callback.message.edit_text(
            _payment_text(appointment),
            reply_markup=_payment_markup(appointment, appointment_id),
        )
    )


async def _answer_payment_screen(message: Message, appointment_id: int):
    try:
        appointment = await get_appointment(appointment_id)
    except Exception:
        await message.answer(
            "Запись не найдена.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await message.answer(
        _payment_text(appointment),
        reply_markup=_payment_markup(appointment, appointment_id),
    )


@payment_router.callback_query(F.data.startswith("pay:start:"))
async def on_pay_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    appointment_id = int(callback.data.split(":")[2])
    await _payment_screen(callback, appointment_id)


@payment_router.callback_query(F.data.startswith("pay:insalon:"))
async def on_pay_insalon(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    appointment_id = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        f"Запись №{appointment_id} создана. Оплатите при посещении салона.\n"
        "Мы вас ждём!",
        reply_markup=to_menu_keyboard(),
    )


@payment_router.callback_query(F.data.startswith("pay:promo:"))
async def on_pay_promo(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    appointment_id = int(callback.data.split(":")[2])
    await state.set_state(PromoStates.code)
    await state.update_data(
        appointment_id=appointment_id,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
    )
    await _safe_edit(
        callback.message.edit_text(
            "Введите промокод, чтобы получить скидку на услугу:",
            reply_markup=None,
        )
    )
    prompt = await callback.message.answer(
        "Отправьте код текстом в чат (или нажмите «Отмена»):",
        reply_markup=promo_input_keyboard(),
    )
    await state.update_data(prompt_message_id=prompt.message_id)


@payment_router.callback_query(F.data.startswith("pay:promo_clear:"))
async def on_pay_promo_clear(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    appointment_id = int(callback.data.split(":")[2])
    try:
        await clear_promo_code(appointment_id)
    except PromoCodeError:
        await _payment_screen(callback, appointment_id)
        return
    except Exception:
        await _payment_screen(callback, appointment_id)
        return
    await _payment_screen(callback, appointment_id)


@payment_router.message(PromoStates.code)
async def on_promo_code(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    data = await state.get_data()
    appointment_id = data["appointment_id"]
    if text in ("Отмена", MENU_BUTTON):
        await state.clear()
        await _try_delete_prompt(bot, data)
        await message.answer("Отменено.", reply_markup=remove_keyboard())
        await _answer_payment_screen(message, appointment_id)
        return
    try:
        await apply_promo_code(appointment_id, text)
    except PromoCodeError as e:
        await message.answer(
            f"{e}\nПопробуйте ещё раз или нажмите «Отмена».",
            reply_markup=promo_input_keyboard(),
        )
        return
    except Exception:
        await message.answer(
            "Не удалось применить промокод. Попробуйте ещё раз.",
            reply_markup=promo_input_keyboard(),
        )
        return
    await state.clear()
    await _try_delete_prompt(bot, data)
    await _answer_payment_screen(message, appointment_id)


@payment_router.callback_query(F.data.startswith("pay:method:"))
async def on_pay_method(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    _, _, method, appointment_id = callback.data.split(":")
    appointment_id = int(appointment_id)
    label = PAYMENT_METHOD_LABELS.get(method, method)
    await callback.message.edit_text(
        f"Обработка платежа…\nСпособ: {label}\nСумма уточняется…"
    )
    await asyncio.sleep(2)
    try:
        appointment = await pay_appointment(appointment_id, method)
    except AlreadyPaidError:
        await callback.message.edit_text(
            f"Запись №{appointment_id} уже оплачена ранее.",
            reply_markup=to_menu_keyboard(),
        )
        return
    except Exception:
        await callback.message.edit_text(
            "Не удалось обработать платёж (имитация). Попробуйте ещё раз.",
            reply_markup=payment_method_keyboard(appointment_id),
        )
        return
    info = await sync_to_async(lambda: {
        "appointment_id": appointment.id,
        "service_name": appointment.service.name,
        "price": appointment.service.price,
        "final_price": appointment.final_price,
        "discount": appointment.discount_amount,
        "payment_id": appointment.payment_id,
    })()
    amount = info["final_price"] or info["price"]
    lines = [
        "Оплата прошла успешно! (имитация)\n\n",
        f"Запись №{info['appointment_id']}\n",
        f"Процедура: {info['service_name']}\n",
    ]
    if info["discount"]:
        lines.append(f"Скидка по промокоду: −{info['discount']} руб.\n")
    lines += [
        f"Сумма: {amount} руб.\n",
        f"Способ: {label}\n",
        f"Номер транзакции: {info['payment_id']}\n\n",
        f"Статус записи: Оплачено. Сумма: {amount} руб. Ждём вас в салоне!",
    ]
    await callback.message.edit_text(
        "".join(lines),
        reply_markup=to_menu_keyboard(),
    )
