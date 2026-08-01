from datetime import datetime

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

from .keyboards import (
    contact_keyboard,
    pf_dates_keyboard,
    pf_masters_keyboard,
    pf_salons_keyboard,
    pf_services_keyboard,
    pf_times_keyboard,
    start_menu_keyboard,
    terms_keyboard,
    to_menu_keyboard,
)
from .services import (
    get_procedure_dates,
    get_procedure_salons,
    get_procedure_times,
    get_services,
    get_time_masters,
    has_terms_consent,
    resolve_slot,
)
from .states import ProcedureFirstStates

procedure_router = Router()
procedure_router.callback_query.middleware(CallbackAnswerMiddleware())


@procedure_router.callback_query(F.data == "flow:procedure")
async def on_flow_procedure(callback: CallbackQuery, state: FSMContext):
    services = await get_services()
    if not services:
        await callback.message.edit_text(
            "Пока нет доступных процедур. Попробуйте позже.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await state.set_state(ProcedureFirstStates.service)
    await callback.message.edit_text(
        "Выберите процедуру:",
        reply_markup=pf_services_keyboard(services),
    )


@procedure_router.callback_query(
    StateFilter(ProcedureFirstStates.service), F.data.startswith("pf:service:")
)
async def on_pf_service(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split(":")[2])
    dates = await get_procedure_dates(service_id)
    if not dates:
        await callback.message.edit_text(
            "Свободных окон по этой процедуре пока нет. "
            "Попробуйте другую или зайдите позже.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await state.update_data(service_id=service_id)
    await state.set_state(ProcedureFirstStates.date)
    await callback.message.edit_text(
        "Выберите дату:",
        reply_markup=pf_dates_keyboard(dates),
    )


@procedure_router.callback_query(
    StateFilter(ProcedureFirstStates.date), F.data.startswith("pf:date:")
)
async def on_pf_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[2]
    slot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    data = await state.get_data()
    times = await get_procedure_times(data["service_id"], slot_date)
    if not times:
        await callback.message.edit_text(
            "Свободного времени на эту дату нет. Выберите другую дату."
        )
        return
    await state.update_data(slot_date=date_str)
    await state.set_state(ProcedureFirstStates.time)
    await callback.message.edit_text(
        "Выберите время:",
        reply_markup=pf_times_keyboard(times),
    )


@procedure_router.callback_query(
    StateFilter(ProcedureFirstStates.time), F.data.startswith("pf:time:")
)
async def on_pf_time(callback: CallbackQuery, state: FSMContext):
    time_str = callback.data.split(":", 2)[2]
    slot_time = datetime.strptime(time_str, "%H:%M").time()
    data = await state.get_data()
    slot_date = datetime.strptime(data["slot_date"], "%Y-%m-%d").date()
    masters = await get_time_masters(data["service_id"], slot_date, slot_time)
    if not masters:
        await callback.message.edit_text(
            "На это время мастеров пока нет. Выберите другое время."
        )
        return
    await state.update_data(slot_time=time_str)
    await state.set_state(ProcedureFirstStates.master)
    await callback.message.edit_text(
        "Выберите мастера:",
        reply_markup=pf_masters_keyboard(masters),
    )


@procedure_router.callback_query(
    StateFilter(ProcedureFirstStates.master), F.data.startswith("pf:master:")
)
async def on_pf_master(callback: CallbackQuery, state: FSMContext):
    master_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    slot_date = datetime.strptime(data["slot_date"], "%Y-%m-%d").date()
    slot_time = datetime.strptime(data["slot_time"], "%H:%M").time()
    salons = await get_procedure_salons(
        data["service_id"], master_id, slot_date, slot_time
    )
    if not salons:
        await callback.message.edit_text(
            "Мастер не принимает по этой процедуре в выбранное время. "
            "Выберите другого мастера или время."
        )
        return
    await state.update_data(master_id=master_id)
    await state.set_state(ProcedureFirstStates.salon)
    await callback.message.edit_text(
        "Выберите салон:",
        reply_markup=pf_salons_keyboard(salons),
    )


@procedure_router.callback_query(
    StateFilter(ProcedureFirstStates.salon), F.data.startswith("pf:salon:")
)
async def on_pf_salon(callback: CallbackQuery, state: FSMContext):
    salon_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    slot_date = datetime.strptime(data["slot_date"], "%Y-%m-%d").date()
    slot_time = datetime.strptime(data["slot_time"], "%H:%M").time()
    slot = await resolve_slot(
        data["service_id"], data["master_id"], salon_id, slot_date, slot_time
    )
    if not slot:
        await callback.message.edit_text(
            "Это время уже заняли. Выберите другой салон или начните заново.",
            reply_markup=to_menu_keyboard(),
        )
        return
    await state.update_data(salon_id=salon_id, slot_id=slot.id)
    if await has_terms_consent(callback.from_user.id):
        await state.set_state(ProcedureFirstStates.contact)
        await callback.message.answer(
            "Почти готово! Поделитесь номером телефона или введите его вручную:",
            reply_markup=contact_keyboard(),
        )
    else:
        await state.set_state(ProcedureFirstStates.terms)
        await callback.message.edit_text(
            "Для записи нам нужно ваше согласие на обработку персональных данных.\n"
            "Подтвердите, что согласны:",
            reply_markup=terms_keyboard(),
        )


@procedure_router.callback_query(
    StateFilter(
        ProcedureFirstStates.service,
        ProcedureFirstStates.date,
        ProcedureFirstStates.time,
        ProcedureFirstStates.master,
        ProcedureFirstStates.salon,
        ProcedureFirstStates.terms,
    ),
    F.data == "back",
)
async def on_back(callback: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    data = await state.get_data()

    if current == ProcedureFirstStates.service.state:
        await state.clear()
        await callback.message.edit_text(
            "Здравствуйте! Это бот записи в салон красоты.\nКак удобнее записаться?",
            reply_markup=start_menu_keyboard(),
        )
    elif current == ProcedureFirstStates.date.state:
        services = await get_services()
        await state.set_state(ProcedureFirstStates.service)
        await callback.message.edit_text(
            "Выберите процедуру:",
            reply_markup=pf_services_keyboard(services),
        )
    elif current == ProcedureFirstStates.time.state:
        dates = await get_procedure_dates(data["service_id"])
        await state.set_state(ProcedureFirstStates.date)
        await callback.message.edit_text(
            "Выберите дату:",
            reply_markup=pf_dates_keyboard(dates),
        )
    elif current == ProcedureFirstStates.master.state:
        slot_date = datetime.strptime(data["slot_date"], "%Y-%m-%d").date()
        slot_time = datetime.strptime(data["slot_time"], "%H:%M").time()
        times = await get_procedure_times(data["service_id"], slot_date)
        await state.set_state(ProcedureFirstStates.time)
        await callback.message.edit_text(
            "Выберите время:",
            reply_markup=pf_times_keyboard(times),
        )
    elif current == ProcedureFirstStates.salon.state:
        slot_date = datetime.strptime(data["slot_date"], "%Y-%m-%d").date()
        slot_time = datetime.strptime(data["slot_time"], "%H:%M").time()
        masters = await get_time_masters(data["service_id"], slot_date, slot_time)
        await state.set_state(ProcedureFirstStates.master)
        await callback.message.edit_text(
            "Выберите мастера:",
            reply_markup=pf_masters_keyboard(masters),
        )
    elif current == ProcedureFirstStates.terms.state:
        slot_date = datetime.strptime(data["slot_date"], "%Y-%m-%d").date()
        slot_time = datetime.strptime(data["slot_time"], "%H:%M").time()
        salons = await get_procedure_salons(
            data["service_id"], data["master_id"], slot_date, slot_time
        )
        await state.set_state(ProcedureFirstStates.salon)
        await callback.message.edit_text(
            "Выберите салон:",
            reply_markup=pf_salons_keyboard(salons),
        )
