from datetime import datetime

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

from .keyboards import (
    active_masters_keyboard,
    contact_keyboard,
    fm_dates_keyboard,
    fm_times_keyboard,
    master_salons_keyboard,
    master_services_keyboard,
    start_menu_keyboard,
    terms_keyboard,
    to_menu_keyboard,
)
from .services import (
    get_active_masters,
    get_fm_dates,
    get_fm_slots,
    get_master_salons,
    get_master_services,
    has_terms_consent,
)
from .states import MasterFirstStates

master_router = Router()
master_router.callback_query.middleware(CallbackAnswerMiddleware())


@master_router.callback_query(F.data == "flow:master")
async def on_flow_master(callback: CallbackQuery, state: FSMContext):
    masters = await get_active_masters()
    if not masters:
        await callback.message.edit_text(
            "Пока нет доступных мастеров. Попробуйте позже.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await state.set_state(MasterFirstStates.master)
    await callback.message.edit_text(
        "Выберите любимого мастера:",
        reply_markup=active_masters_keyboard(masters),
    )


@master_router.callback_query(
    StateFilter(MasterFirstStates.master), F.data.startswith("fm:master:")
)
async def on_fm_master(callback: CallbackQuery, state: FSMContext):
    master_id = int(callback.data.split(":")[2])
    services = await get_master_services(master_id)
    if not services:
        await callback.message.edit_text(
            "У этого мастера пока нет процедур. Выберите другого.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await state.update_data(master_id=master_id)
    await state.set_state(MasterFirstStates.service)
    await callback.message.edit_text(
        "Выберите процедуру:",
        reply_markup=master_services_keyboard(services),
    )


@master_router.callback_query(
    StateFilter(MasterFirstStates.service), F.data.startswith("fm:service:")
)
async def on_fm_service(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    salons = await get_master_salons(data["master_id"])
    if not salons:
        await callback.message.edit_text(
            "Мастер сейчас не принимает ни в одном салоне. Попробуйте позже.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await state.update_data(service_id=service_id)
    await state.set_state(MasterFirstStates.salon)
    await callback.message.edit_text(
        "Выберите салон:",
        reply_markup=master_salons_keyboard(salons),
    )


@master_router.callback_query(
    StateFilter(MasterFirstStates.salon), F.data.startswith("fm:salon:")
)
async def on_fm_salon(callback: CallbackQuery, state: FSMContext):
    salon_id = int(callback.data.split(":")[2])
    await state.update_data(salon_id=salon_id)
    data = await state.get_data()
    dates = await get_fm_dates(data["master_id"], salon_id)
    if not dates:
        await callback.message.edit_text(
            "Свободных окон у мастера пока нет. Попробуйте другой салон или позже.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await state.set_state(MasterFirstStates.date)
    await callback.message.edit_text(
        "Выберите дату:",
        reply_markup=fm_dates_keyboard(dates),
    )


@master_router.callback_query(
    StateFilter(MasterFirstStates.date), F.data.startswith("fm:date:")
)
async def on_fm_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[2]
    slot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    await state.update_data(slot_date=date_str)
    data = await state.get_data()
    slots = await get_fm_slots(data["master_id"], data["salon_id"], slot_date)
    if not slots:
        await callback.message.edit_text(
            "Свободного времени на эту дату нет. Выберите другую дату."
        )
        return
    await state.set_state(MasterFirstStates.time)
    await callback.message.edit_text(
        "Выберите время:",
        reply_markup=fm_times_keyboard(slots),
    )


@master_router.callback_query(
    StateFilter(MasterFirstStates.time), F.data.startswith("fm:time:")
)
async def on_fm_time(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split(":")[2])
    await state.update_data(slot_id=slot_id)
    if await has_terms_consent(callback.from_user.id):
        await state.set_state(MasterFirstStates.contact)
        await callback.message.answer(
            "Почти готово! Поделитесь номером телефона или введите его вручную:",
            reply_markup=contact_keyboard(),
        )
    else:
        await state.set_state(MasterFirstStates.terms)
        await callback.message.edit_text(
            "Для записи нам нужно ваше согласие на обработку персональных данных.\n"
            "Подтвердите, что согласны:",
            reply_markup=terms_keyboard(),
        )


@master_router.callback_query(
    StateFilter(
        MasterFirstStates.master,
        MasterFirstStates.service,
        MasterFirstStates.salon,
        MasterFirstStates.date,
        MasterFirstStates.time,
        MasterFirstStates.terms,
    ),
    F.data == "back",
)
async def on_back(callback: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    data = await state.get_data()

    if current == MasterFirstStates.master.state:
        await state.clear()
        await callback.message.edit_text(
            "Здравствуйте! Это бот записи в салон красоты.\nКак удобнее записаться?",
            reply_markup=start_menu_keyboard(),
        )
    elif current == MasterFirstStates.service.state:
        masters = await get_active_masters()
        await state.set_state(MasterFirstStates.master)
        await callback.message.edit_text(
            "Выберите мастера:",
            reply_markup=active_masters_keyboard(masters),
        )
    elif current == MasterFirstStates.salon.state:
        services = await get_master_services(data["master_id"])
        await state.set_state(MasterFirstStates.service)
        await callback.message.edit_text(
            "Выберите процедуру:",
            reply_markup=master_services_keyboard(services),
        )
    elif current == MasterFirstStates.date.state:
        salons = await get_master_salons(data["master_id"])
        await state.set_state(MasterFirstStates.salon)
        await callback.message.edit_text(
            "Выберите салон:",
            reply_markup=master_salons_keyboard(salons),
        )
    elif current == MasterFirstStates.time.state:
        dates = await get_fm_dates(data["master_id"], data["salon_id"])
        await state.set_state(MasterFirstStates.date)
        await callback.message.edit_text(
            "Выберите дату:",
            reply_markup=fm_dates_keyboard(dates),
        )
    elif current == MasterFirstStates.terms.state:
        slot_date = datetime.strptime(data["slot_date"], "%Y-%m-%d").date()
        slots = await get_fm_slots(data["master_id"], data["salon_id"], slot_date)
        await state.set_state(MasterFirstStates.time)
        await callback.message.edit_text(
            "Выберите время:",
            reply_markup=fm_times_keyboard(slots),
        )
