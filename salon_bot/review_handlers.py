from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

from .keyboards import (
    MENU_BUTTON,
    remove_keyboard,
    review_rating_keyboard,
    review_text_keyboard,
    review_visits_keyboard,
    start_menu_keyboard,
    to_menu_keyboard,
)
from .payment_handlers import _try_delete_prompt
from .services import create_review, get_appointment, get_client_review_visits
from .states import ReviewStates

review_router = Router()
review_router.callback_query.middleware(CallbackAnswerMiddleware())


@review_router.callback_query(F.data == "review:start")
async def on_review_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    visits = await get_client_review_visits(callback.from_user.id)
    if not visits:
        await callback.message.edit_text(
            "Пока нет завершённых визитов, к которым можно оставить отзыв.\n"
            "Как только услуга будет завершена, здесь появится форма обратной связи.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await callback.message.edit_text(
        "Выберите визит, о котором хотите оставить отзыв:",
        reply_markup=review_visits_keyboard(visits),
    )


@review_router.callback_query(F.data.startswith("review:pick:"))
async def on_review_pick(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    appointment_id = int(callback.data.split(":")[2])
    await state.set_state(ReviewStates.rating)
    await state.update_data(appointment_id=appointment_id, telegram_id=callback.from_user.id)
    try:
        appointment = await get_appointment(appointment_id)
    except Exception:
        await callback.message.edit_text(
            "Запись не найдена.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await callback.message.edit_text(
        "Отзыв о визите\n\n"
        f"Мастер: {appointment.slot.master.full_name}\n"
        f"Услуга: {appointment.service.name}\n"
        f"Дата: {appointment.slot.date.strftime('%d.%m.%Y')}\n\n"
        "Оцените работу специалиста (1 — плохо, 5 — отлично):",
        reply_markup=review_rating_keyboard(appointment_id),
    )


@review_router.callback_query(F.data.startswith("review:rate:"))
async def on_review_rate(callback: CallbackQuery, state: FSMContext):
    _, _, appointment_id, rating = callback.data.split(":")
    rating = int(rating)
    await state.update_data(rating=rating)
    await state.set_state(ReviewStates.text)
    await callback.message.edit_text(
        f"Спасибо! Ваша оценка: {rating}/5.\n"
        "Теперь напишите пару слов о визите:",
        reply_markup=None,
    )
    prompt = await callback.message.answer(
        "Что вам понравилось? (или нажмите «Отмена»):",
        reply_markup=review_text_keyboard(),
    )
    await state.update_data(
        prompt_message_id=prompt.message_id,
        chat_id=callback.message.chat.id,
    )


@review_router.message(ReviewStates.text)
async def on_review_text(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    data = await state.get_data()
    if text in ("Отмена", MENU_BUTTON):
        await state.clear()
        await _try_delete_prompt(bot, data)
        await message.answer("Отзыв отменён.", reply_markup=remove_keyboard())
        await message.answer(
            "Здравствуйте! Это бот записи в салон красоты.\nКак удобнее записаться?",
            reply_markup=start_menu_keyboard(),
        )
        return
    if len(text) < 3:
        await message.answer(
            "Отзыв слишком короткий. Расскажите чуть подробнее:",
            reply_markup=review_text_keyboard(),
        )
        return
    await create_review(data["telegram_id"], data["appointment_id"], data["rating"], text)
    await state.clear()
    await _try_delete_prompt(bot, data)
    await message.answer(
        "Спасибо за ваш отзыв! Он очень важен для нас.\n"
        "Оценка и отзыв переданы мастеру.",
        reply_markup=remove_keyboard(),
    )
    await message.answer(
        "Здравствуйте! Это бот записи в салон красоты.\nКак удобнее записаться?",
        reply_markup=start_menu_keyboard(),
    )
