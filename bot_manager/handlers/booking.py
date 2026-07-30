import datetime
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async

from bot_manager.models import Client, TimeSlot, Appointment, Salon, Service, Master
from bot_manager.handlers.states_utils import (
    BookingProcess, SalonCallback, ServiceCallback, MasterCallback, SlotCallback
)

waiting_feedback = {}
booking_router = Router()

# ==========================================
# ФУНКЦИОНАЛ ОТРИСОВКИ ШАГОВ (ИНТЕРФЕЙС)
# ==========================================

async def show_salon_selection(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    
    def query_salons():
        qs = Salon.objects.all()
        if 'master' in user_data:
            qs = qs.filter(master__id=user_data['master'])
        return list(qs)
        
    salons = await sync_to_async(query_salons)()
    builder = InlineKeyboardBuilder()
    
    for s in salons:
        builder.button(text=s.name, callback_data=SalonCallback(id=s.id).pack())
    
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main")
    builder.adjust(1)
    
    await message.edit_text("📍 Выберите желаемый салон красоты:", reply_markup=builder.as_markup())
    await state.set_state(BookingProcess.step_salon)


async def show_service_selection(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    flow = user_data.get('flow')
    
    def query_services():
        # Если в памяти уже есть мастер (Флоу №2 «Любимый мастер»)
        if 'master' in user_data:
            return list(Service.objects.filter(master__id=user_data['master']).distinct())
            
        # Если мы зашли со стороны салона (Флоу №1 «Ближайший салон»)
        elif 'salon' in user_data:
            # Находим мастеров этого салона, у которых есть свободные слоты
            active_masters = TimeSlot.objects.filter(
                salon_id=user_data['salon'],
                is_booked=False,
                date__gte=datetime.date.today()
            ).values_list('master_id', flat=True).distinct()
            
            # Фильтруем услуги через обратную связь master_set
            return list(Service.objects.filter(master__in=active_masters).distinct())
            
        # Флоу №3: Мы зашли со стороны процедур («Мне нужна процедура»)
        elif flow == "service":
            # Выбираем ID всех мастеров, у которых есть свободные окошки в будущем
            available_master_ids = TimeSlot.objects.filter(
                is_booked=False,
                date__gte=datetime.date.today()
            ).values_list('master_id', flat=True).distinct()
            
            # Показываем только те услуги, которые эти мастера умеют делать
            return list(Service.objects.filter(master__in=available_master_ids).distinct())
            
        # Резервный вариант (на всякий случай)
        return list(Service.objects.all())
        
    services = await sync_to_async(query_services)()
    builder = InlineKeyboardBuilder()
    
    for s in services:
        builder.button(text=f"{s.name} — {int(s.price)} руб.", callback_data=ServiceCallback(id=s.id).pack())
        
    builder.button(text="⬅️ Назад", callback_data="step_back")
    builder.adjust(1)
    
    await message.edit_text("💇 Выберите необходимую процедуру:", reply_markup=builder.as_markup())
    await state.set_state(BookingProcess.step_service)


async def show_master_selection(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    
    def query_masters():
        qs = Master.objects.filter(is_active=True)
        if 'salon' in user_data:
            qs = qs.filter(salons__id=user_data['salon'])
        if 'service' in user_data:
            qs = qs.filter(services__id=user_data['service'])
        return list(qs)
        
    masters = await sync_to_async(query_masters)()
    builder = InlineKeyboardBuilder()
    
    for m in masters:
        builder.button(text=m.full_name, callback_data=MasterCallback(id=m.id).pack())
        
    builder.button(text="⬅️ Назад", callback_data="step_back")
    builder.adjust(1)
    
    await message.edit_text("⭐ Выберите специалиста:", reply_markup=builder.as_markup())
    await state.set_state(BookingProcess.step_master)


async def show_date_time_selection(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    def query_slots():
    # 1. Базовые фильтры (не занято и дата не в прошлом)
        filters = {
            'is_booked': False,
            'date__gte': datetime.date.today()
        }
        
        # 2. Динамически добавляем мастера (если он уже выбран во флоу)
        if user_data.get('master'):
            filters['master_id'] = user_data['master']
            
        # 3. Динамически добавляем салон (если он уже выбран во флоу)
        if user_data.get('salon'):
            filters['salon_id'] = user_data['salon']
            
        # 4. Фильтр по услуге для Флоу №3 ("хочу процедуру")
        # Если мастер и салон еще не выбраны, но услуга уже известна:
        if user_data.get('service') and not user_data.get('master') and not user_data.get('salon'):
            filters['master__services__id'] = user_data['service'] 

        return list(TimeSlot.objects.filter(**filters).order_by('date', 'time').distinct()[:12])
        
    slots = await sync_to_async(query_slots)()
    builder = InlineKeyboardBuilder()
    
    for slot in slots:
        btn_text = f"📅 {slot.date.strftime('%d.%m')} в {slot.time.strftime('%H:%M')}"
        builder.button(text=btn_text, callback_data=SlotCallback(id=slot.id).pack())
        
    builder.button(text="⬅️ Назад", callback_data="step_back")
    builder.adjust(2)
    
    if not slots:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Начать сначала", callback_data="back_to_main")
        await message.edit_text(
            "❌ К сожалению, на выбранные параметры нет свободных окон.\n"
            "Попробуйте выбрать другого мастера или салон.", 
            reply_markup=builder.as_markup()
        )
        return
        
    await message.edit_text("⏰ Выберите свободное и удобное время записи:", reply_markup=builder.as_markup())
    await state.set_state(BookingProcess.step_date_time)


async def request_phone(message: types.Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass

    phone_keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)]
        ],
        resize_keyboard=True, 
        one_time_keyboard=True
    )
    
    await message.answer(
        "Пожалуйста, поделитесь своим номером телефона для подтверждения бронирования:",
        reply_markup=phone_keyboard
    )
    await state.set_state(BookingProcess.entering_phone)


# ==========================================
# ОБРАБОТЧИКИ НАЖАТИЙ (ДИСПЕТЧЕРЫ)
# ==========================================

@booking_router.callback_query(SalonCallback.filter(), BookingProcess.step_salon)
async def process_salon_step(callback: types.CallbackQuery, callback_data: SalonCallback, state: FSMContext):
    await state.update_data(salon=callback_data.id)
    user_data = await state.get_data()
    flow = user_data['flow']
    
    if flow == "salon":        
        await show_service_selection(callback.message, state)
    elif flow == "master":     
        await show_date_time_selection(callback.message, state)
    elif flow == "service":    
        await request_phone(callback.message, state)
    await callback.answer()


@booking_router.callback_query(ServiceCallback.filter(), BookingProcess.step_service)
async def process_service_step(callback: types.CallbackQuery, callback_data: ServiceCallback, state: FSMContext):
    await state.update_data(service=callback_data.id)
    user_data = await state.get_data()
    flow = user_data['flow']
    
    if flow == "salon":        
        await show_master_selection(callback.message, state)
    elif flow == "master":     
        await show_salon_selection(callback.message, state)
    elif flow == "service":    
        await show_date_time_selection(callback.message, state)
    await callback.answer()


@booking_router.callback_query(MasterCallback.filter(), BookingProcess.step_master)
async def process_master_step(callback: types.CallbackQuery, callback_data: MasterCallback, state: FSMContext):
    await state.update_data(master=callback_data.id)
    user_data = await state.get_data()
    flow = user_data['flow']
    
    if flow == "salon":        
        await show_date_time_selection(callback.message, state)
    elif flow == "master":     
        await show_service_selection(callback.message, state)
    elif flow == "service":    
        await show_salon_selection(callback.message, state)
    await callback.answer()


@booking_router.callback_query(SlotCallback.filter(), BookingProcess.step_date_time)
async def process_slot_step(callback: types.CallbackQuery, callback_data: SlotCallback, state: FSMContext):
    await state.update_data(slot=callback_data.id)
    user_data = await state.get_data()
    flow = user_data['flow']
    
    if flow == "service":
        def extract_info_from_slot():
            slot = TimeSlot.objects.select_related('master', 'salon').get(id=callback_data.id)
            return slot.master.id, slot.salon.id
            
        master_id, salon_id = await sync_to_async(extract_info_from_slot)()
        await state.update_data(master=master_id, salon=salon_id)
        await show_master_selection(callback.message, state)
    else:
        await request_phone(callback.message, state)
        
    await callback.answer()


# ==========================================
# ОБРАБОТКА КОНТАКТНЫХ ДАННЫХ И ФИНАЛИЗАЦИЯ
# ==========================================

@booking_router.message(F.contact, BookingProcess.entering_phone)
async def finalize_appointment_contact(message: types.Message, state: FSMContext, bot: Bot):
    phone = message.contact.phone_number
    await process_appointment_creation(message, state, phone, bot=bot)


@booking_router.message(F.text, BookingProcess.entering_phone)
async def finalize_appointment_text(message: types.Message, state: FSMContext, bot: Bot):
    phone = message.text.strip()
    if not any(char.isdigit() for char in phone) or len(phone) < 7:
        await message.answer("Пожалуйста, введите корректный номер телефона (например, +79XXXXXXXXX):")
        return
    await process_appointment_creation(message, state, phone, bot=bot)


async def process_appointment_creation(message: types.Message, state: FSMContext, phone: str, bot: Bot):
    user_data = await state.get_data()
    
    if 'slot' not in user_data or 'service' not in user_data:
        await message.answer(
            "⚠️ Сессия устарела. Пожалуйста, начните запись заново через команду /start",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()
        return

    def db_transaction():
        client, _ = Client.objects.get_or_create(
            telegram_id=message.from_user.id,
            defaults={'username': message.from_user.username or ""}
        )
        client.phone = phone
        client.save()
        
        try:
            slot = TimeSlot.objects.select_related('salon', 'master').get(id=user_data['slot'])
            if slot.is_booked:
                return None  
                
            slot.is_booked = True
            slot.save()
            
            return Appointment.objects.create(
                client=client,
                slot=slot,
                service_id=user_data['service'],
                status='pending'
            )
        except TimeSlot.DoesNotExist:
            return None

    appointment = await sync_to_async(db_transaction)()
    
    if not appointment:
        await message.answer(
            "❌ Ошибка: это время только что занял другой клиент! Попробуйте выбрать другое время: /start", 
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()
        return

    # Запрашиваем связанные данные для красивого вывода
    salon_name = await sync_to_async(lambda: appointment.slot.salon.name)()
    master_name = await sync_to_async(lambda: appointment.slot.master.full_name)()
    service_name = await sync_to_async(lambda: appointment.service.name)()
    slot_date = await sync_to_async(lambda: appointment.slot.date)()
    slot_time = await sync_to_async(lambda: appointment.slot.time)()

    feedback_builder = InlineKeyboardBuilder()
    feedback_builder.button(
        text="Оставить отзыв",
        callback_data=f"leave_feedback_{appointment.id}"
    )
    feedback_builder.adjust(1)

    # Отправляем сообщение об успешной записи
    await message.answer(
        f"🎉 *Запись успешно оформлена!*\n\n"
        f"📍 *Салон:* {salon_name}\n"
        f"💇 *Процедура:* {service_name}\n"
        f"👤 *Специалист:* {master_name}\n"
        f"⏰ *Время визита:* {slot_date.strftime('%d.%m.%Y')} в {slot_time.strftime('%H:%M')}\n\n"
        f"Ждем вас!",
        reply_markup=feedback_builder.as_markup(),
        parse_mode="Markdown"
    )

    await state.clear()

# ==========================================
# НАВИГАЦИЯ НАЗАД (УМНЫЕ КНОПКИ)
# ==========================================

@booking_router.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: types.CallbackQuery, state: FSMContext):
    from bot_manager.handlers.start import show_main_menu
    await state.clear()
    await callback.message.delete()
    await show_main_menu(callback.message, state, callback.from_user.first_name)
    await callback.answer()


@booking_router.callback_query(F.data == "step_back")
async def process_step_back(callback: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_state = await state.get_state()
    flow = user_data.get('flow')

    # --- ЭТАП: ВЫБОР УСЛУГИ ---
    if current_state == BookingProcess.step_service:
        user_data.pop('service', None)
        await state.set_data(user_data)
        
        if flow == "salon": 
            await state.set_state(BookingProcess.step_salon)
            await show_salon_selection(callback.message, state)
        elif flow == "master": 
            await state.set_state(BookingProcess.step_master)
            await show_master_selection(callback.message, state)
        elif flow == "service": 
            from bot_manager.handlers.start import show_main_menu
            await state.clear()
            await callback.message.delete()
            await show_main_menu(callback.message, state, callback.from_user.first_name)
            await callback.answer()
            return

    # --- ЭТАП: ВЫБОР МАСТЕРА ---
    elif current_state == BookingProcess.step_master:
        user_data.pop('master', None)
        # Если мы во флоу Процедуры, то на шаг мастера мы пришли из Даты/Времени.
        # При возврате назад нужно стереть автоматически определенные салон и слот.
        if flow == "service":
            user_data.pop('slot', None)
            user_data.pop('salon', None)
        await state.set_data(user_data)
        
        if flow == "salon": 
            await state.set_state(BookingProcess.step_service)
            await show_service_selection(callback.message, state)
        elif flow == "service": 
            await state.set_state(BookingProcess.step_date_time)
            await show_date_time_selection(callback.message, state)

    # --- ЭТАП: ВЫБОР САЛОНА ---
    elif current_state == BookingProcess.step_salon:
        user_data.pop('salon', None)
        await state.set_data(user_data)
        
        if flow == "master": 
            await state.set_state(BookingProcess.step_service)
            await show_service_selection(callback.message, state)
        elif flow == "service": 
            await state.set_state(BookingProcess.step_master)
            await show_master_selection(callback.message, state)

    # --- ЭТАП: ВЫБОР ДАТЫ И ВРЕМЕНИ ---
    elif current_state == BookingProcess.step_date_time:
        user_data.pop('slot', None)
        await state.set_data(user_data)
        
        if flow == "salon": 
            await state.set_state(BookingProcess.step_master)
            await show_master_selection(callback.message, state)
        elif flow == "master": 
            await state.set_state(BookingProcess.step_salon)
            await show_salon_selection(callback.message, state)
        elif flow == "service": 
            await state.set_state(BookingProcess.step_service)
            await show_service_selection(callback.message, state)

    # Гасим анимацию часиков на кнопке Telegram
    await callback.answer()


# ================================================================
# ОБРАБОТЧИКИ ОТЗЫВОВ
# ================================================================
@booking_router.callback_query(F.data.startswith("leave_feedback_"))
async def ask_feedback(callback: types.CallbackQuery, state: FSMContext):
    appointment_id = int(callback.data.replace("leave_feedback_", ""))

    await callback.answer()
    await callback.message.edit_text(
        "✍️ Напишите ваш отзыв в следующем сообщении (текст):"
    )

    waiting_feedback[callback.from_user.id] = appointment_id


@booking_router.message(F.text)
async def save_feedback(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id in waiting_feedback:
        appointment_id = waiting_feedback.pop(user_id)

        try:
            appointment = await sync_to_async(Appointment.objects.get)(id=appointment_id)
            appointment.feedback = message.text
            appointment.feedback_asked = True
            await sync_to_async(appointment.save)()

            salon_name = await sync_to_async(lambda: appointment.slot.salon.name)()
            master_name = await sync_to_async(lambda: appointment.slot.master.full_name)()
            service_name = await sync_to_async(lambda: appointment.service.name)()
            slot_date = await sync_to_async(lambda: appointment.slot.date)()
            slot_time = await sync_to_async(lambda: appointment.slot.time)()

            await message.answer(
                f"✅ Спасибо за ваш отзыв! Мы ценим ваше мнение.\n\n"
                f"🎉 *Запись успешно оформлена!*\n\n"
                f"📍 *Салон:* {salon_name}\n"
                f"💇 *Процедура:* {service_name}\n"
                f"👤 *Специалист:* {master_name}\n"
                f"⏰ *Время визита:* {slot_date.strftime('%d.%m.%Y')} в {slot_time.strftime('%H:%M')}\n\n"
                f"Ждем вас!",
                parse_mode="Markdown"
            )

        except Appointment.DoesNotExist:
            await message.answer("Запись не найдена. Возможно, она уже удалена.")
    else:
        await message.answer("Спасибо за сообщение! Если это отзыв, вы можете оставить его в любое время.")
