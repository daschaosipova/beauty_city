from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from decimal import Decimal

from bot_manager.models import Appointment
from bot_manager.payment_service import PaymentService

payment_router = Router()
payment_service = PaymentService()

class PaymentStates(StatesGroup):
    choosing_tips = State()
    confirming_payment = State()
    waiting_for_tips = State()

# ==========================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ЧАЕВЫМИ
# ==========================================

def create_tips_keyboard(appointment_id: int):
    """Создает клавиатуру для выбора чаевых"""
    builder = InlineKeyboardBuilder()
    
    # Предустановленные суммы чаевых
    tips_options = [
        ("Без чаевых", "0"),
        ("5%", "5"),
        ("10%", "10"),
        ("15%", "15"),
        ("Своя сумма", "custom")
    ]
    
    for label, value in tips_options:
        builder.button(text=label, callback_data=f"tips_{value}_{appointment_id}")
    
    builder.button(text="❌ Отмена", callback_data="cancel_payment")
    builder.adjust(2)  # По 2 кнопки в ряд
    
    return builder.as_markup()

async def show_payment_options(message: types.Message, appointment_id: int, total_amount: Decimal, state: FSMContext):
    """Показывает варианты оплаты и чаевые"""
    
    # Получаем данные о записи
    def get_appointment_data():
        try:
            appointment = Appointment.objects.select_related(
                'service', 'slot__master', 'slot__salon'
            ).get(id=appointment_id)
            
            # Создаем чаевые по умолчанию (10%)
            default_tips = appointment.service.price * Decimal('0.10')
            
            return {
                'service_name': appointment.service.name,
                'service_price': appointment.service.price,
                'master_name': appointment.slot.master.full_name,
                'salon_name': appointment.slot.salon.name,
                'date': appointment.slot.date,
                'time': appointment.slot.time,
                'default_tips': default_tips,
                'total': appointment.service.price + default_tips
            }
        except Appointment.DoesNotExist:
            return None
    
    data = await sync_to_async(get_appointment_data)()
    if not data:
        await message.answer("❌ Запись не найдена. Попробуйте снова.")
        return
    
    await state.update_data(appointment_id=appointment_id)
    await state.set_state(PaymentStates.choosing_tips)    

    # Формируем сообщение
    text = (
        f"💰 *Оплата записи*\n\n"
        f"💇 Услуга: {data['service_name']}\n"
        f"👤 Мастер: {data['master_name']}\n"
        f"📍 Салон: {data['salon_name']}\n"
        f"📅 Дата: {data['date'].strftime('%d.%m.%Y')}\n"
        f"⏰ Время: {data['time'].strftime('%H:%M')}\n\n"
        f"💵 Стоимость услуги: {data['service_price']} руб.\n"
        f"💝 Рекомендуемые чаевые (10%): {data['default_tips']} руб.\n"
        f"💰 Итого: {data['total']} руб.\n\n"
        f"Выберите размер чаевых:"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=create_tips_keyboard(appointment_id)
    )
    
    # Сохраняем appointment_id в состоянии
    # Нужно использовать FSMContext

# ==========================================
# ОБРАБОТЧИКИ ОПЛАТЫ
# ==========================================

@payment_router.callback_query(F.data.startswith("tips_"))
async def process_tips_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор чаевых"""
    tips_value = callback.data.replace("tips_", "")
    
    # Получаем данные из состояния
    user_data = await state.get_data()
    appointment_id = user_data.get('appointment_id')
    
    if not appointment_id:
        await callback.answer("❌ Сессия устарела. Начните заново.")
        return
    
    # Получаем цену услуги
    def get_service_price():
        try:
            appointment = Appointment.objects.select_related('service').get(id=appointment_id)
            return appointment.service.price
        except Appointment.DoesNotExist:
            return None
    
    service_price = await sync_to_async(get_service_price)()
    if service_price is None:
        await callback.answer("❌ Запись не найдена.")
        return
    
    # Рассчитываем чаевые
    if tips_value == "custom":
        await callback.message.edit_text(
            "✏️ Введите сумму чаевых в рублях (числом):\n"
            "(например: 500 или 0, если не хотите)"
        )
        await state.set_state(PaymentStates.waiting_for_tips)
        await callback.answer()
        return
    
    tips_percent = Decimal(tips_value) / Decimal('100')
    tips_amount = service_price * tips_percent
    
    # Сохраняем чаевые
    await state.update_data(tips_amount=tips_amount)
    
    # Показываем подтверждение
    await show_payment_confirmation(callback.message, state, service_price, tips_amount)
    await callback.answer(f"Чаевые: {tips_amount} руб.")


@payment_router.message(PaymentStates.waiting_for_tips)
async def process_custom_tips(message: types.Message, state: FSMContext):
    """Обрабатывает ввод своей суммы чаевых"""
    try:
        tips_amount = Decimal(message.text.replace(',', '.'))
        if tips_amount < 0:
            raise ValueError("Сумма не может быть отрицательной")
    except (ValueError, TypeError):
        await message.answer("❌ Пожалуйста, введите корректное число (например: 500)")
        return
    
    # Сохраняем чаевые
    user_data = await state.get_data()
    appointment_id = user_data.get('appointment_id')
    
    if not appointment_id:
        await message.answer("❌ Сессия устарела. Начните заново.")
        return
    
    # Получаем цену услуги
    def get_service_price():
        try:
            appointment = Appointment.objects.select_related('service').get(id=appointment_id)
            return appointment.service.price
        except Appointment.DoesNotExist:
            return None
    
    service_price = await sync_to_async(get_service_price)()
    if service_price is None:
        await message.answer("❌ Запись не найдена.")
        return
    
    await state.update_data(tips_amount=tips_amount)
    await show_payment_confirmation(message, state, service_price, tips_amount)


async def show_payment_confirmation(message: types.Message, state: FSMContext, service_price: Decimal, tips_amount: Decimal):
    """Показывает подтверждение оплаты"""
    total = service_price + tips_amount
    
    # Создаем клавиатуру для подтверждения
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Оплатить", callback_data="confirm_payment_{appointment_id}")
    builder.button(text="✏️ Изменить чаевые", callback_data="change_tips")
    builder.button(text="❌ Отменить", callback_data="cancel_payment")
    builder.adjust(1)
    
    text = (
        f"💳 *Подтверждение оплаты*\n\n"
        f"💵 Стоимость услуги: {service_price} руб.\n"
        f"💝 Чаевые: {tips_amount} руб.\n"
        f"💰 ИТОГО: {total} руб.\n\n"
        f"Нажмите «Оплатить» для перехода к платежной системе."
    )
    
    await message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    
    await state.update_data(total_amount=total)
    await state.set_state(PaymentStates.confirming_payment)


@payment_router.callback_query(F.data.startswith("confirm_payment_"), PaymentStates.confirming_payment)
async def process_payment(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение оплаты"""
    user_data = await state.get_data()
    appointment_id = user_data.get('appointment_id')
    tips_amount = user_data.get('tips_amount', Decimal('0'))
    total_amount = user_data.get('total_amount')
    
    if not appointment_id:
        await callback.answer("❌ Сессия устарела.")
        return
    
    # Создаем платеж
    payment_data = await payment_service.create_payment(
        appointment_id=appointment_id,
        amount=total_amount,
        description=f"Оплата услуг + чаевые"
    )
    
    if payment_data and payment_data.get('confirmation_url'):
        # Сохраняем чаевые
        def update_appointment_tips():
            try:
                appointment = Appointment.objects.get(id=appointment_id)
                appointment.tips_amount = tips_amount
                appointment.save()
                return True
            except Appointment.DoesNotExist:
                return False
        
        await sync_to_async(update_appointment_tips)()
        
        # Отправляем ссылку на оплату
        builder = InlineKeyboardBuilder()
        builder.button(text="💳 Перейти к оплате", url=payment_data['confirmation_url'])
        builder.button(text="🔄 Проверить оплату", callback_data=f"check_payment_{payment_data['payment_id']}")
        builder.button(text="❌ Отменить", callback_data="cancel_payment")
        builder.adjust(1)
        
        await callback.message.edit_text(
            "🔗 *Перейдите по ссылке для оплаты*\n\n"
            f"Сумма: {total_amount} руб.\n"
            "После оплаты нажмите «Проверить оплату»",
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при создании платежа. Попробуйте позже."
        )
    
    await callback.answer()


@payment_router.callback_query(F.data.startswith("check_payment_"))
async def check_payment(callback: types.CallbackQuery, state: FSMContext):
    """Проверяет статус платежа"""
    payment_id = callback.data.replace("check_payment_", "")
    
    result = await payment_service.check_payment_status(payment_id)
    
    if result.get('paid'):
        # Получаем данные о записи
        def get_appointment_data():
            try:
                appointment = Appointment.objects.select_related(
                    'client',
                    'service',
                    'slot__master',
                    'slot__salon'
                ).get(payment_id=payment_id)
                return appointment
            except Appointment.DoesNotExist:
                return None
        
        appointment = await sync_to_async(get_appointment_data)()
        
        if appointment:
            # Данные для уведомления
            salon_name = appointment.slot.salon.name
            master_name = appointment.slot.master.full_name
            service_name = appointment.service.name
            slot_date = appointment.slot.date
            slot_time = appointment.slot.time

            # Обновляем сообщение об оплате
            await callback.message.edit_text(
                "✅ *Платеж успешно выполнен!*\n\n",
                parse_mode="Markdown"
            )
            
            # Отправляем данные о записи
            await callback.message.answer(
                f"🎉 *Запись успешно оформлена!*\n\n"
                f"📍 *Салон:* {salon_name}\n"
                f"💇 *Процедура:* {service_name}\n"
                f"👤 *Специалист:* {master_name}\n"
                f"⏰ *Время визита:* {slot_date.strftime('%d.%m.%Y')} в {slot_time.strftime('%H:%M')}\n"
                f"Ждем вас!",
                parse_mode="Markdown"
            )
            
            await state.clear()
        
    elif result.get('status') == 'pending':
        await callback.answer("⏳ Платеж еще не завершен. Попробуйте через минуту.", show_alert=True)
    else:
        await callback.answer("❌ Платеж не прошел. Попробуйте снова.", show_alert=True)


@payment_router.callback_query(F.data == "change_tips")
async def change_tips(callback: types.CallbackQuery, state: FSMContext):
    """Позволяет изменить чаевые"""
    user_data = await state.get_data()
    appointment_id = user_data.get('appointment_id')
    
    if appointment_id:
        await callback.message.edit_text(
            "✏️ Введите новую сумму чаевых в рублях (числом):"
        )
        await state.set_state(PaymentStates.waiting_for_tips)
    else:
        await callback.answer("❌ Ошибка. Начните заново.")
    
    await callback.answer()


@payment_router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет оплату"""
    await state.clear()
    
    await callback.message.edit_text(
        "❌ Оплата отменена.\n"
        "Вы можете записаться снова через /start"
    )
    await callback.answer()


@payment_router.callback_query(F.data == "confirm_booking")
async def confirm_booking(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждает запись после оплаты"""
    await callback.message.edit_text(
        "✅ Ваша запись подтверждена!\n\n"
        "Мы ждем вас в салоне. Спасибо за выбор! 💫"
    )

    payment_id = callback.data.replace("check_payment_", "")
    def get_appointment_data():
        try:
            appointment = Appointment.objects.select_related(
                'client',
                'service',
                'slot__master',
                'slot__salon'
            ).get(payment_id=payment_id)
            return appointment
        except Appointment.DoesNotExist:
            return None
            
    appointment = await sync_to_async(get_appointment_data)()
        
    if appointment:
        # Данные для уведомления
        salon_name = appointment.slot.salon.name
        master_name = appointment.slot.master.full_name
        service_name = appointment.service.name
        slot_date = appointment.slot.date
        slot_time = appointment.slot.time
        tips = appointment.tips_amount
        
        # Обновляем сообщение об оплате
        await callback.message.edit_text(
            "✅ *Платеж успешно выполнен!*\n\n"
            "Ваша запись подтверждена. Ждем вас в салоне! 💫",
            parse_mode="Markdown"
        )
        
        # Отправляем данные о записи
        await callback.message.answer(
            f"🎉 *Запись успешно оформлена!*\n\n"
            f"📍 *Салон:* {salon_name}\n"
            f"💇 *Процедура:* {service_name}\n"
            f"👤 *Специалист:* {master_name}\n"
            f"⏰ *Время визита:* {slot_date.strftime('%d.%m.%Y')} в {slot_time.strftime('%H:%M')}\n"
            f"💝 *Чаевые:* {tips} руб.\n\n"
            f"Ждем вас!",
            parse_mode="Markdown"
        )
    
    await state.clear()
    await callback.answer()