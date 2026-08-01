from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

WEEKDAYS = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
MENU_BUTTON = "Выход в главное меню"


def salons_keyboard(salons) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for salon in salons:
        kb.button(text=f"{salon.name} ({salon.address})", callback_data=f"salon:{salon.id}")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def start_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Выбрать салон", callback_data="flow:salon")
    kb.button(text="К любимому мастеру", callback_data="flow:master")
    kb.button(text="Мне нужна процедура", callback_data="flow:procedure")
    kb.button(text="Хочу записаться по телефону", callback_data="flow:phone")
    kb.button(text="Хочу оставить отзыв", callback_data="review:start")
    kb.button(text="Выход", callback_data="exit")
    kb.adjust(1)
    return kb.as_markup()


def to_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def phone_salons_keyboard(salons) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for salon in salons:
        kb.button(
            text=f"{salon.name} ({salon.address})",
            callback_data=f"phone:salon:{salon.id}",
        )
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def phone_back_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="К списку салонов", callback_data="phone:list")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def pf_services_keyboard(services) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for service in services:
        kb.button(
            text=f"{service.name} — {service.price} руб.",
            callback_data=f"pf:service:{service.id}",
        )
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def pf_dates_keyboard(dates) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for date in dates:
        label = f"{date.strftime('%d.%m.%Y')} ({WEEKDAYS[date.weekday()]})"
        kb.button(text=label, callback_data=f"pf:date:{date.isoformat()}")
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def pf_times_keyboard(times) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for slot_time in times:
        kb.button(text=slot_time.strftime("%H:%M"), callback_data=f"pf:time:{slot_time.strftime('%H:%M')}")
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(3)
    return kb.as_markup()


def pf_masters_keyboard(masters) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for master in masters:
        kb.button(text=master.full_name, callback_data=f"pf:master:{master.id}")
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def pf_salons_keyboard(salons) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for salon in salons:
        kb.button(
            text=f"{salon.name} ({salon.address})",
            callback_data=f"pf:salon:{salon.id}",
        )
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def active_masters_keyboard(masters) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for master in masters:
        kb.button(text=master.full_name, callback_data=f"fm:master:{master.id}")
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def master_services_keyboard(services) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for service in services:
        kb.button(
            text=f"{service.name} — {service.price} руб.",
            callback_data=f"fm:service:{service.id}",
        )
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def master_salons_keyboard(salons) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for salon in salons:
        kb.button(
            text=f"{salon.name} ({salon.address})",
            callback_data=f"fm:salon:{salon.id}",
        )
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def fm_dates_keyboard(dates) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for date in dates:
        label = f"{date.strftime('%d.%m.%Y')} ({WEEKDAYS[date.weekday()]})"
        kb.button(text=label, callback_data=f"fm:date:{date.isoformat()}")
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def fm_times_keyboard(slots) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for slot in slots:
        kb.button(text=slot.time.strftime("%H:%M"), callback_data=f"fm:time:{slot.id}")
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(3)
    return kb.as_markup()


def services_keyboard(services) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for service in services:
        kb.button(text=service.name, callback_data=f"service:{service.id}")
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def price_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Продолжить", callback_data="price_next")
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def masters_keyboard(masters) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for master in masters:
        kb.button(text=master.full_name, callback_data=f"master:{master.id}")
    kb.button(text="Любой мастер", callback_data="master:any")
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def dates_keyboard(dates) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for date in dates:
        label = f"{date.strftime('%d.%m.%Y')} ({WEEKDAYS[date.weekday()]})"
        kb.button(text=label, callback_data=f"date:{date.isoformat()}")
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def times_keyboard(slots) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for slot in slots:
        kb.button(text=slot.time.strftime("%H:%M"), callback_data=f"time:{slot.id}")
    kb.button(text="Назад", callback_data="back")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(3)
    return kb.as_markup()


def terms_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Согласен", callback_data="terms_agree")
    kb.button(text="Не согласен", callback_data="terms_decline")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поделиться номером", request_contact=True)],
            [KeyboardButton(text=MENU_BUTTON)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Подтвердить запись", callback_data="confirm_yes")
    kb.button(text="Отменить", callback_data="confirm_no")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def staff_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Оформить запись по телефону", callback_data="staff:new")
    kb.button(text="Чаевые", callback_data="staff:tips")
    kb.button(text="Выход", callback_data="exit")
    kb.adjust(1)
    return kb.as_markup()


def staff_tips_keyboard(appointments) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for app in appointments:
        label = (
            f"№{app.id} — {app.slot.master.full_name} — {app.client.phone or 'клиент'}"
            f" ({app.slot.date.strftime('%d.%m.%Y')})"
        )
        kb.button(text=label, callback_data=f"st:tips_link:{app.id}")
    kb.button(text="Назад", callback_data="staff:back_menu")
    kb.button(text="Выйти", callback_data="staff:exit")
    kb.adjust(1)
    return kb.as_markup()


def staff_salons_keyboard(salons) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for salon in salons:
        kb.button(
            text=f"{salon.name} ({salon.address})",
            callback_data=f"st:salon:{salon.id}",
        )
    kb.button(text="Назад", callback_data="staff:back")
    kb.button(text="Выйти", callback_data="staff:exit")
    kb.adjust(1)
    return kb.as_markup()


def staff_services_keyboard(services) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for service in services:
        kb.button(
            text=f"{service.name} — {service.price} руб.",
            callback_data=f"st:service:{service.id}",
        )
    kb.button(text="Назад", callback_data="staff:back")
    kb.button(text="Выйти", callback_data="staff:exit")
    kb.adjust(1)
    return kb.as_markup()


def staff_masters_keyboard(masters) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for master in masters:
        kb.button(text=master.full_name, callback_data=f"st:master:{master.id}")
    kb.button(text="Любой мастер", callback_data="st:master:any")
    kb.button(text="Назад", callback_data="staff:back")
    kb.button(text="Выйти", callback_data="staff:exit")
    kb.adjust(1)
    return kb.as_markup()


def staff_dates_keyboard(dates) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for date in dates:
        label = f"{date.strftime('%d.%m.%Y')} ({WEEKDAYS[date.weekday()]})"
        kb.button(text=label, callback_data=f"st:date:{date.isoformat()}")
    kb.button(text="Назад", callback_data="staff:back")
    kb.button(text="Выйти", callback_data="staff:exit")
    kb.adjust(1)
    return kb.as_markup()


def staff_times_keyboard(slots) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for slot in slots:
        kb.button(text=slot.time.strftime("%H:%M"), callback_data=f"st:time:{slot.id}")
    kb.button(text="Назад", callback_data="staff:back")
    kb.button(text="Выйти", callback_data="staff:exit")
    kb.adjust(3)
    return kb.as_markup()


def staff_confirm_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Подтвердить запись", callback_data="st:confirm_yes")
    kb.button(text="Изменить данные", callback_data="staff:back")
    kb.button(text="Отменить", callback_data="st:confirm_no")
    kb.adjust(1)
    return kb.as_markup()


def staff_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def promo_input_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def review_visits_keyboard(visits) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for visit in visits:
        label = (
            f"№{visit.id} — {visit.slot.master.full_name} "
            f"({visit.slot.date.strftime('%d.%m.%Y')})"
        )
        kb.button(text=label, callback_data=f"review:pick:{visit.id}")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def review_rating_keyboard(appointment_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for n in range(1, 6):
        kb.button(text=str(n), callback_data=f"review:rate:{appointment_id}:{n}")
    kb.button(text=MENU_BUTTON, callback_data="to_menu")
    kb.adjust(5)
    return kb.as_markup()


def review_text_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def payment_choice_keyboard(appointment_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Оплатить онлайн", callback_data=f"pay:start:{appointment_id}")
    kb.button(text="Оплатить в салоне", callback_data=f"pay:insalon:{appointment_id}")
    kb.button(text="Вернуться в меню", callback_data="to_menu")
    kb.adjust(1)
    return kb.as_markup()


def payment_method_keyboard(appointment_id, has_promo=False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Банковская карта", callback_data=f"pay:method:card:{appointment_id}")
    kb.button(text="СБП (СБПэй)", callback_data=f"pay:method:sbp:{appointment_id}")
    if has_promo:
        kb.button(text="Сбросить промокод", callback_data=f"pay:promo_clear:{appointment_id}")
    else:
        kb.button(text="Применить промокод", callback_data=f"pay:promo:{appointment_id}")
    kb.button(text="Оплатить в салоне", callback_data=f"pay:insalon:{appointment_id}")
    kb.button(text="Назад", callback_data=f"pay:start:{appointment_id}")
    kb.adjust(1)
    return kb.as_markup()


def tip_amount_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for amount in (100, 200, 300, 500):
        kb.button(text=f"{amount} руб.", callback_data=f"tip:amount:{amount}")
    kb.button(text="Своя сумма", callback_data="tip:amount:custom")
    kb.button(text="Не хочу чаевые", callback_data="tip:cancel")
    kb.adjust(2)
    return kb.as_markup()


def tip_method_keyboard(amount) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"Банковская карта ({amount} руб.)",
        callback_data=f"tip:method:card:{amount}",
    )
    kb.button(
        text=f"СБП (СБПэй) ({amount} руб.)",
        callback_data=f"tip:method:sbp:{amount}",
    )
    kb.button(text="← Изменить сумму", callback_data="tip:back_amount")
    kb.adjust(1)
    return kb.as_markup()


def tip_custom_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
