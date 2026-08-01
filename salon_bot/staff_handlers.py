import hmac
import os
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message
from aiogram.utils.callback_answer import CallbackAnswerMiddleware
from asgiref.sync import sync_to_async

from .keyboards import (
    staff_confirm_keyboard,
    staff_dates_keyboard,
    staff_masters_keyboard,
    staff_menu_keyboard,
    staff_phone_keyboard,
    staff_salons_keyboard,
    staff_services_keyboard,
    staff_times_keyboard,
    staff_tips_keyboard,
    to_menu_keyboard,
)
from .services import (
    SlotAlreadyBookedError,
    TipsError,
    create_appointment,
    generate_tips_token,
    get_appointment,
    get_available_dates,
    get_free_slots,
    get_masters,
    get_or_create_client_by_phone,
    get_services,
    get_salons,
    get_tips_eligible_appointments,
)
from .shared_handlers import PHONE_PATTERN, _summary_text
from .states import StaffStates

staff_router = Router()
staff_router.callback_query.middleware(CallbackAnswerMiddleware())


def _check_password(password):
    expected = os.getenv("STAFF_PASSWORD", "")
    return bool(expected) and hmac.compare_digest(password, expected)


async def _safe_edit(awaitable):
    try:
        await awaitable
    except TelegramBadRequest as e:
        if "message is not modified" not in e.message:
            raise


@staff_router.errors.register
async def on_staff_error(event: ErrorEvent):
    if (
        isinstance(event.exception, TelegramBadRequest)
        and "message is not modified" in event.exception.message
    ):
        return
    raise event.exception


async def _staff_menu(message: Message):
    await message.answer(
        "Панель сотрудника. Что делаем?",
        reply_markup=staff_menu_keyboard(),
    )


@staff_router.message(Command("staff"))
async def on_staff_cmd(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(StaffStates.auth)
    await message.answer(
        "Скрытый раздел сотрудника.\nВведите пароль для входа:"
    )


@staff_router.message(StateFilter(StaffStates.auth), F.text)
async def on_staff_auth(message: Message, state: FSMContext):
    if not _check_password(message.text.strip()):
        await message.answer("Неверный пароль. Попробуйте ещё раз или /cancel")
        return
    await state.clear()
    await _staff_menu(message)


@staff_router.callback_query(F.data == "staff:tips")
async def on_staff_tips(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    appointments = await get_tips_eligible_appointments()
    if not appointments:
        await _safe_edit(
            callback.message.edit_text(
                "Нет завершённых визитов, по которым ещё не отправлены чаевые.",
                reply_markup=staff_menu_keyboard(),
            )
        )
        return
    await _safe_edit(
        callback.message.edit_text(
            "Выберите запись — для неё будет создана ссылка на чаевые:",
            reply_markup=staff_tips_keyboard(appointments),
        )
    )


@staff_router.callback_query(F.data == "staff:back_menu")
async def on_staff_back_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _safe_edit(
        callback.message.edit_text(
            "Панель сотрудника. Что делаем?",
            reply_markup=staff_menu_keyboard(),
        )
    )


@staff_router.callback_query(F.data.startswith("st:tips_link:"))
async def on_staff_tips_link(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    appointment_id = int(callback.data.split(":")[2])
    try:
        token = await generate_tips_token(appointment_id)
    except TipsError as e:
        await _safe_edit(
            callback.message.edit_text(
                str(e),
                reply_markup=staff_menu_keyboard(),
            )
        )
        return
    appointment = await get_appointment(appointment_id)
    info = await sync_to_async(lambda: {
        "client_tg": appointment.client.telegram_id,
        "master_name": appointment.slot.master.full_name,
    })()
    me = await callback.bot.me()
    link = f"https://t.me/{me.username}?start=tip_{token}"
    sent_to_client = False
    if info["client_tg"] and info["client_tg"] > 0:
        try:
            await callback.bot.send_message(
                info["client_tg"],
                "Спасибо, что были у нас!\n"
                f"Если хотите, вы можете оставить чаевые мастеру "
                f"{info['master_name']} по ссылке:\n{link}",
            )
            sent_to_client = True
        except Exception:
            sent_to_client = False
    if sent_to_client:
        text = (
            f"Ссылка на чаевые для записи №{appointment_id} "
            "создана и отправлена клиенту в Telegram."
        )
    else:
        text = (
            f"Ссылка на чаевые для записи №{appointment_id}:\n\n"
            f"{link}\n\nОтправьте её клиенту самостоятельно."
        )
    await _safe_edit(
        callback.message.edit_text(
            text,
            reply_markup=staff_menu_keyboard(),
        )
    )


@staff_router.callback_query(F.data == "staff:new")
async def on_staff_new(callback: CallbackQuery, state: FSMContext):
    salons = await get_salons()
    if not salons:
        await callback.message.edit_text(
            "Пока нет доступных салонов. Попробуйте позже.",
            reply_markup=staff_menu_keyboard(),
        )
        return
    await state.set_state(StaffStates.salon)
    await callback.message.edit_text(
        "Оформляем запись по звонку.\nВыберите салон:",
        reply_markup=staff_salons_keyboard(salons),
    )


@staff_router.callback_query(StateFilter(StaffStates.salon), F.data.startswith("st:salon:"))
async def on_staff_salon(callback: CallbackQuery, state: FSMContext):
    salon_id = int(callback.data.split(":")[2])
    await state.update_data(salon_id=salon_id)
    services = await get_services()
    if not services:
        await callback.message.edit_text(
            "Услуги пока не добавлены. Попробуйте позже.",
            reply_markup=staff_menu_keyboard(),
        )
        return
    await state.set_state(StaffStates.service)
    await callback.message.edit_text(
        "Выберите процедуру:",
        reply_markup=staff_services_keyboard(services),
    )


@staff_router.callback_query(StateFilter(StaffStates.service), F.data.startswith("st:service:"))
async def on_staff_service(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split(":")[2])
    await state.update_data(service_id=service_id)
    data = await state.get_data()
    masters = await get_masters(data["salon_id"], service_id)
    if not masters:
        await callback.message.edit_text(
            "Специалистов по этой процедуре в салоне нет. Попробуйте другой салон.",
            reply_markup=staff_menu_keyboard(),
        )
        return
    await state.set_state(StaffStates.master)
    await callback.message.edit_text(
        "Выберите мастера (или «Любой мастер»):",
        reply_markup=staff_masters_keyboard(masters),
    )


@staff_router.callback_query(StateFilter(StaffStates.master), F.data.startswith("st:master:"))
async def on_staff_master(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[2]
    master_id = None if value == "any" else int(value)
    await state.update_data(master_id=master_id)
    data = await state.get_data()
    dates = await get_available_dates(master_id, data["salon_id"], data["service_id"])
    if not dates:
        await callback.message.edit_text(
            "Свободных окон нет. Попробуйте другого мастера или позже.",
            reply_markup=staff_menu_keyboard(),
        )
        return
    await state.set_state(StaffStates.date)
    await callback.message.edit_text(
        "Выберите дату:",
        reply_markup=staff_dates_keyboard(dates),
    )


@staff_router.callback_query(StateFilter(StaffStates.date), F.data.startswith("st:date:"))
async def on_staff_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[2]
    slot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    await state.update_data(slot_date=date_str)
    data = await state.get_data()
    slots = await get_free_slots(
        data["master_id"], data["salon_id"], data["service_id"], slot_date
    )
    if not slots:
        await callback.message.edit_text(
            "Свободного времени на эту дату нет. Выберите другую дату.",
            reply_markup=staff_menu_keyboard(),
        )
        return
    await state.set_state(StaffStates.time)
    await callback.message.edit_text(
        "Выберите время:",
        reply_markup=staff_times_keyboard(slots),
    )


@staff_router.callback_query(StateFilter(StaffStates.time), F.data.startswith("st:time:"))
async def on_staff_time(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split(":")[2])
    await state.update_data(slot_id=slot_id)
    await state.set_state(StaffStates.phone)
    await callback.message.answer(
        "Введите номер телефона клиента (например, +7 999 123-45-67):",
        reply_markup=staff_phone_keyboard(),
    )


@staff_router.message(StateFilter(StaffStates.phone), F.text == "Отмена")
async def on_staff_phone_cancel(message: Message, state: FSMContext):
    await state.clear()
    await _staff_menu(message)


@staff_router.message(StateFilter(StaffStates.phone), F.text)
async def on_staff_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not PHONE_PATTERN.fullmatch(phone):
        await message.answer(
            "Номер не похож на телефон. Попробуйте ещё раз:",
            reply_markup=staff_phone_keyboard(),
        )
        return
    client = await get_or_create_client_by_phone(phone)
    await state.update_data(client_id=client.id)
    await state.set_state(StaffStates.confirm)
    data = await state.get_data()
    await message.answer(
        f"Клиент: {client.phone}\n\n"
        "Проверьте запись:\n" + await _summary_text(data),
        reply_markup=staff_confirm_keyboard(),
    )


@staff_router.callback_query(StateFilter(StaffStates.confirm), F.data == "st:confirm_yes")
async def on_staff_confirm_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        appointment = await create_appointment(
            data["client_id"], data["slot_id"], data["service_id"]
        )
    except SlotAlreadyBookedError:
        await state.clear()
        await callback.message.edit_text(
            "Это время уже заняли (например, клиент записался через бот). "
            "Выберите другое время.",
            reply_markup=staff_menu_keyboard(),
        )
        return
    appointment_id = appointment.id
    info = await sync_to_async(lambda: {
        "client_phone": appointment.client.phone,
        "client_tg": appointment.client.telegram_id,
        "salon_name": appointment.slot.salon.name,
        "master_name": appointment.slot.master.full_name,
        "slot_date": appointment.slot.date,
        "slot_time": appointment.slot.time,
        "service_name": appointment.service.name,
    })()
    await state.clear()
    await callback.message.edit_text(
        f"Запись оформлена! Номер записи: {appointment_id}\n"
        f"Клиент: {info['client_phone']}\n"
        f"Салон: {info['salon_name']}\n"
        f"Мастер: {info['master_name']}\n"
        f"Дата: {info['slot_date'].strftime('%d.%m.%Y')}\n"
        f"Время: {info['slot_time'].strftime('%H:%M')}\n\n"
        "Слот заблокирован — через бот он больше не покажется.",
        reply_markup=staff_menu_keyboard(),
    )
    if info["client_tg"] and info["client_tg"] > 0:
        try:
            await callback.bot.send_message(
                info["client_tg"],
                f"Вы записаны по телефону!\n"
                f"Запись №{appointment_id}: {info['service_name']}\n"
                f"{info['salon_name']}\n"
                f"{info['slot_date'].strftime('%d.%m.%Y')} "
                f"в {info['slot_time'].strftime('%H:%M')}\n"
                f"Мастер: {info['master_name']}",
            )
        except Exception:
            pass


@staff_router.callback_query(StateFilter(StaffStates.confirm), F.data == "st:confirm_no")
async def on_staff_confirm_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Запись отменена.",
        reply_markup=staff_menu_keyboard(),
    )


@staff_router.callback_query(StateFilter(StaffStates.salon), F.data == "staff:back")
async def on_staff_back_from_salon(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Панель сотрудника. Что делаем?",
        reply_markup=staff_menu_keyboard(),
    )


@staff_router.callback_query(
    StateFilter(
        StaffStates.service,
        StaffStates.master,
        StaffStates.date,
        StaffStates.time,
        StaffStates.confirm,
    ),
    F.data == "staff:back",
)
async def on_staff_back(callback: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    data = await state.get_data()

    if current == StaffStates.service.state:
        salons = await get_salons()
        await state.set_state(StaffStates.salon)
        await callback.message.edit_text(
            "Выберите салон:",
            reply_markup=staff_salons_keyboard(salons),
        )
    elif current == StaffStates.master.state:
        services = await get_services()
        await state.set_state(StaffStates.service)
        await callback.message.edit_text(
            "Выберите процедуру:",
            reply_markup=staff_services_keyboard(services),
        )
    elif current == StaffStates.date.state:
        masters = await get_masters(data["salon_id"], data["service_id"])
        await state.set_state(StaffStates.master)
        await callback.message.edit_text(
            "Выберите мастера (или «Любой мастер»):",
            reply_markup=staff_masters_keyboard(masters),
        )
    elif current == StaffStates.time.state:
        dates = await get_available_dates(
            data["master_id"], data["salon_id"], data["service_id"]
        )
        await state.set_state(StaffStates.date)
        await callback.message.edit_text(
            "Выберите дату:",
            reply_markup=staff_dates_keyboard(dates),
        )
    elif current == StaffStates.confirm.state:
        await state.set_state(StaffStates.phone)
        await callback.message.answer(
            "Введите номер телефона клиента (например, +7 999 123-45-67):",
            reply_markup=staff_phone_keyboard(),
        )


@staff_router.callback_query(F.data == "staff:exit")
async def on_staff_exit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Вы вышли из раздела сотрудника.",
        reply_markup=to_menu_keyboard(),
    )
