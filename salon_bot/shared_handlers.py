import re

from asgiref.sync import sync_to_async
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

from .keyboards import (
    MENU_BUTTON,
    confirm_keyboard,
    contact_keyboard,
    payment_choice_keyboard,
    remove_keyboard,
    start_menu_keyboard,
    terms_keyboard,
    to_menu_keyboard,
)
from .services import (
    SlotAlreadyBookedError,
    create_appointment,
    get_salon,
    get_service,
    get_slot,
    save_client,
)
from .states import BookingStates, MasterFirstStates, ProcedureFirstStates

shared_router = Router()
shared_router.callback_query.middleware(CallbackAnswerMiddleware())

PHONE_PATTERN = re.compile(r"^[+\d][\d\s\-()]{5,19}$")

_CONTACT_BY_STATE = {
    MasterFirstStates.terms.state: MasterFirstStates.contact,
    ProcedureFirstStates.terms.state: ProcedureFirstStates.contact,
}
_CONFIRM_BY_STATE = {
    MasterFirstStates.contact.state: MasterFirstStates.confirm,
    ProcedureFirstStates.contact.state: ProcedureFirstStates.confirm,
}


def _price_text(service):
    return (
        f"Процедура: {service.name}\n"
        f"Цена: {service.price} руб.\n"
        f"Длительность: {service.duration_minutes} мин."
    )


async def _summary_text(data):
    salon = await get_salon(data["salon_id"])
    service = await get_service(data["service_id"])
    slot = await get_slot(data["slot_id"])
    return "\n".join(
        [
            f"Салон: {salon.name} ({salon.address})",
            f"Процедура: {service.name}",
            f"Цена: {service.price} руб.",
            f"Мастер: {slot.master.full_name}",
            f"Дата: {slot.date.strftime('%d.%m.%Y')}",
            f"Время: {slot.time.strftime('%H:%M')}",
        ]
    )


@shared_router.callback_query(
    StateFilter(BookingStates.terms, MasterFirstStates.terms, ProcedureFirstStates.terms),
    F.data == "terms_agree",
)
async def on_terms_agree(callback: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    contact_state = _CONTACT_BY_STATE.get(current, BookingStates.contact)
    await state.set_state(contact_state)
    await callback.message.answer(
        "Почти готово! Нажмите «Поделиться номером» или введите номер текстом:",
        reply_markup=contact_keyboard(),
    )


@shared_router.callback_query(
    StateFilter(BookingStates.terms, MasterFirstStates.terms, ProcedureFirstStates.terms),
    F.data == "terms_decline",
)
async def on_terms_decline(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Жаль. Без согласия на обработку данных мы не можем оформить запись. "
        "Если передумаете.",
        reply_markup=to_menu_keyboard(),
    )


@shared_router.message(
    StateFilter(BookingStates.contact, MasterFirstStates.contact, ProcedureFirstStates.contact),
    F.contact,
)
async def on_contact(message: Message, state: FSMContext):
    await _finish_contact(message, state, message.contact.phone_number)


@shared_router.message(
    StateFilter(BookingStates.contact, MasterFirstStates.contact, ProcedureFirstStates.contact),
    F.text == MENU_BUTTON,
)
async def on_contact_exit(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Возвращаемся в главное меню.", reply_markup=remove_keyboard())
    await message.answer(
        "Здравствуйте! Это бот записи в салон красоты.\nКак удобнее записаться?",
        reply_markup=start_menu_keyboard(),
    )


@shared_router.message(
    StateFilter(BookingStates.contact, MasterFirstStates.contact, ProcedureFirstStates.contact),
    F.text,
)
async def on_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not PHONE_PATTERN.fullmatch(phone):
        await message.answer(
            "Номер не похож на телефон. Попробуйте ещё раз:",
            reply_markup=contact_keyboard(),
        )
        return
    await _finish_contact(message, state, phone)


async def _finish_contact(message: Message, state: FSMContext, phone: str):
    data = await state.get_data()
    client = await save_client(message.from_user.id, message.from_user.username, phone)
    await state.update_data(client_id=client.id)
    current = await state.get_state()
    confirm_state = _CONFIRM_BY_STATE.get(current, BookingStates.confirm)
    await state.set_state(confirm_state)
    await message.answer("Спасибо!", reply_markup=remove_keyboard())
    await message.answer(
        "Проверьте запись:\n" + await _summary_text(data),
        reply_markup=confirm_keyboard(),
    )


@shared_router.callback_query(
    StateFilter(BookingStates.confirm, MasterFirstStates.confirm, ProcedureFirstStates.confirm),
    F.data == "confirm_yes",
)
async def on_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        appointment = await create_appointment(
            data["client_id"], data["slot_id"], data["service_id"]
        )
    except SlotAlreadyBookedError:
        await state.clear()
        await callback.message.edit_text(
            "К сожалению, это время уже заняли. Попробуйте выбрать другое.",
            reply_markup=to_menu_keyboard(),
        )
        return
    salon = await sync_to_async(lambda: appointment.slot.salon)()
    await state.clear()
    await callback.message.edit_text(
        f"Запись подтверждена! Номер записи: {appointment.id}\n"
        f"Салон: {salon.name}\n"
        f"Адрес: {salon.address}\n"
        f"Телефон салона: {salon.phone}\n\n"
        "Как хотите оплатить?",
        reply_markup=payment_choice_keyboard(appointment.id),
    )


@shared_router.callback_query(
    StateFilter(BookingStates.confirm, MasterFirstStates.confirm, ProcedureFirstStates.confirm),
    F.data == "confirm_no",
)
async def on_confirm_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Запись отменена.",
        reply_markup=to_menu_keyboard(),
    )
