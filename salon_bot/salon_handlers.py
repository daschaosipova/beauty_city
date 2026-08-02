from datetime import datetime

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

from .keyboards import (
    contact_keyboard,
    dates_keyboard,
    masters_keyboard,
    price_keyboard,
    salons_keyboard,
    services_keyboard,
    terms_keyboard,
    times_keyboard,
    to_menu_keyboard,
)
from .services import (
    get_available_dates,
    get_free_slots,
    get_masters,
    get_service,
    get_services,
    get_salons,
    has_terms_consent,
)
from .shared_handlers import _price_text
from .states import BookingStates

salon_router = Router()
salon_router.callback_query.middleware(CallbackAnswerMiddleware())


@salon_router.callback_query(F.data == "flow:salon")
async def on_flow_salon(callback: CallbackQuery, state: FSMContext):
    salons = await get_salons()
    if not salons:
        await callback.message.edit_text("Пока нет доступных салонов. Попробуйте позже.")
        return
    await state.set_state(BookingStates.salon)
    await callback.message.edit_text(
        "Выберите салон:",
        reply_markup=salons_keyboard(salons),
    )


@salon_router.callback_query(StateFilter(BookingStates.salon), F.data.startswith("salon:"))
async def on_salon(callback: CallbackQuery, state: FSMContext):
    salon_id = int(callback.data.split(":", 1)[1])
    await state.update_data(salon_id=salon_id)
    services = await get_services()
    if not services:
        await callback.message.edit_text("Услуги пока не добавлены. Попробуйте позже.")
        return
    await state.set_state(BookingStates.service)
    await callback.message.edit_text(
        "Выберите процедуру:",
        reply_markup=services_keyboard(services),
    )


@salon_router.callback_query(StateFilter(BookingStates.service), F.data.startswith("service:"))
async def on_service(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split(":", 1)[1])
    service = await get_service(service_id)
    await state.update_data(service_id=service_id)
    await state.set_state(BookingStates.price)
    await callback.message.edit_text(_price_text(service), reply_markup=price_keyboard())


@salon_router.callback_query(StateFilter(BookingStates.price), F.data == "price_next")
async def on_price_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    masters = await get_masters(data["salon_id"], data["service_id"])
    if not masters:
        await callback.message.edit_text(
            "Специалистов по этой процедуре в выбранном салоне пока нет. "
            "Попробуйте другой салон или процедуру.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await state.set_state(BookingStates.master)
    await callback.message.edit_text(
        "Выберите мастера:",
        reply_markup=masters_keyboard(masters),
    )


@salon_router.callback_query(StateFilter(BookingStates.master), F.data.startswith("master:"))
async def on_master(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    master_id = None if value == "any" else int(value)
    await state.update_data(master_id=master_id)
    data = await state.get_data()
    dates = await get_available_dates(master_id, data["salon_id"], data["service_id"])
    if not dates:
        await callback.message.edit_text(
            "Свободных окон пока нет. Попробуйте другого мастера или зайдите позже.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await state.set_state(BookingStates.date)
    await callback.message.edit_text("Выберите дату:", reply_markup=dates_keyboard(dates))


@salon_router.callback_query(StateFilter(BookingStates.date), F.data.startswith("date:"))
async def on_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":", 1)[1]
    slot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    await state.update_data(slot_date=date_str)
    data = await state.get_data()
    slots = await get_free_slots(
        data["master_id"], data["salon_id"], data["service_id"], slot_date
    )
    if not slots:
        await callback.message.edit_text(
            "Свободного времени на эту дату нет. Выберите другую дату."
        )
        return
    await state.set_state(BookingStates.time)
    await callback.message.edit_text("Выберите время:", reply_markup=times_keyboard(slots))


@salon_router.callback_query(StateFilter(BookingStates.time), F.data.startswith("time:"))
async def on_time(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split(":", 1)[1])
    await state.update_data(slot_id=slot_id)
    if await has_terms_consent(callback.from_user.id):
        await state.set_state(BookingStates.contact)
        await callback.message.answer(
            "Почти готово! Поделитесь номером телефона или введите его вручную:",
            reply_markup=contact_keyboard(),
        )
    else:
        await state.set_state(BookingStates.terms)
        await callback.message.edit_text(
            "Для записи нам нужно ваше согласие на обработку персональных данных.\n"
            "Подтвердите, что согласны:",
            reply_markup=terms_keyboard(),
        )


@salon_router.callback_query(
    StateFilter(
        BookingStates.service,
        BookingStates.price,
        BookingStates.master,
        BookingStates.date,
        BookingStates.time,
        BookingStates.terms,
    ),
    F.data == "back",
)
async def on_back(callback: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    data = await state.get_data()

    if current == BookingStates.service.state:
        salons = await get_salons()
        await state.set_state(BookingStates.salon)
        await callback.message.edit_text(
            "Выберите салон:",
            reply_markup=salons_keyboard(salons),
        )
    elif current == BookingStates.price.state:
        services = await get_services()
        await state.set_state(BookingStates.service)
        await callback.message.edit_text(
            "Выберите процедуру:",
            reply_markup=services_keyboard(services),
        )
    elif current == BookingStates.master.state:
        service = await get_service(data["service_id"])
        await state.set_state(BookingStates.price)
        await callback.message.edit_text(
            _price_text(service),
            reply_markup=price_keyboard(),
        )
    elif current == BookingStates.date.state:
        masters = await get_masters(data["salon_id"], data["service_id"])
        await state.set_state(BookingStates.master)
        await callback.message.edit_text(
            "Выберите мастера:",
            reply_markup=masters_keyboard(masters),
        )
    elif current == BookingStates.time.state:
        dates = await get_available_dates(
            data["master_id"], data["salon_id"], data["service_id"]
        )
        await state.set_state(BookingStates.date)
        await callback.message.edit_text(
            "Выберите дату:",
            reply_markup=dates_keyboard(dates),
        )
    elif current == BookingStates.terms.state:
        slot_date = datetime.strptime(data["slot_date"], "%Y-%m-%d").date()
        slots = await get_free_slots(
            data["master_id"], data["salon_id"], data["service_id"], slot_date
        )
        await state.set_state(BookingStates.time)
        await callback.message.edit_text(
            "Выберите время:",
            reply_markup=times_keyboard(slots),
        )
