import datetime
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async

from bot_manager.models import Client, TimeSlot, Appointment, Salon, Service, Master, PromoCode
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
    flow = user_data.get('flow')
    
    def query_salons():
        # Базовый запрос
        qs = Salon.objects.all()
        
        # Флоу №2 («Любимый мастер»): Фильтруем салоны, где работает выбранный мастер
        if 'master' in user_data:
            qs = qs.filter(master__id=user_data['master'])
            
        # Флоу №1 («Ближайший салон»): Показываем только те салоны, где есть свободные окна
        elif flow == "salon":
            available_salon_ids = TimeSlot.objects.filter(
                is_booked=False,
                date__gte=datetime.date.today()
            ).values_list('salon_id', flat=True).distinct()
            
            qs = qs.filter(id__in=available_salon_ids)
            
        return list(qs.distinct())
    
        
    salons = await sync_to_async(query_salons)()
    builder = InlineKeyboardBuilder()
    
    for s in salons:
        builder.button(text=s.name, callback_data=SalonCallback(id=s.id).pack())
    
    builder.button(text="⬅️ Назад", callback_data="step_back")
    builder.adjust(1)

    if not salons:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ В главное меню", callback_data="back_to_main")
        await message.edit_text(
            "❌ К сожалению, сейчас нет салонов со свободными окнами для записи.\n"
            "Пожалуйста, попробуйте позже.", 
            reply_markup=builder.as_markup()
        )
        return
    
    await message.edit_text("📍 Выберите желаемый салон красоты:", reply_markup=builder.as_markup())
    await state.set_state(BookingProcess.step_salon)


async def show_service_selection(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    flow = user_data.get('flow')
    promo_code = user_data.get('promo_code')
    
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
        # Рассчитываем цену с учетом промокода
        price_info = await calculate_price_with_discount(s.id, promo_code)

        if promo_code and price_info.get('promo_code'):
            # Если промокод применен - показываем старую и новую цену
            button_text = (
                f"{s.name} — {int(price_info['discounted_price'])} руб. "
                f"(было {int(price_info['original_price'])} руб.) 🔥"
            )
        else:
            # Обычная цена
            button_text = f"{s.name} — {int(s.price)} руб."

        builder.button(text=button_text, callback_data=ServiceCallback(id=s.id).pack())

        # Кнопки для промокода
    if promo_code:
        builder.button(text=f"🎫 Промокод: {promo_code} ✅ (изменить)", callback_data="change_promo")
    else:
        builder.button(text="🎫 Ввести промокод", callback_data="enter_promo_from_services")

    builder.button(text="⬅️ Назад", callback_data="step_back")
    builder.adjust(1)

    # Заголовок с информацией о промокоде
    header = "💇 Выберите необходимую процедуру:"
    if promo_code:
        header = f"💇 Выберите необходимую процедуру:\n🎫 *Промокод {promo_code} применен!*"

    # Пытаемся отредактировать существующее сообщение, если не получается - отправляем новое
    try:
        await message.edit_text(header, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception:
        await message.answer(header, reply_markup=builder.as_markup(), parse_mode="Markdown")

    await state.set_state(BookingProcess.step_service)


async def show_master_selection(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    flow = user_data.get('flow')
    
    def query_masters():
        # 1. Сначала находим ID всех мастеров, у которых есть свободные окна в будущем
        slot_filters = {
            'is_booked': False,
            'date__gte': datetime.date.today()
        }
        
        # Если салон уже выбран (Флоу №1 «Салон») — ищем слоты только в этом салоне
        if 'salon' in user_data:
            slot_filters['salon_id'] = user_data['salon']
            
        available_master_ids = TimeSlot.objects.filter(**slot_filters).values_list('master_id', flat=True).distinct()
        
        # 2. Фильтруем саму модель Master
        qs = Master.objects.filter(is_active=True, id__in=available_master_ids)
        
        # Если услуга уже выбрана (Флоу №1 и Флоу №3) — оставляем мастеров, умеющих её делать
        if 'service' in user_data:
            qs = qs.filter(services__id=user_data['service'])
            
        # На всякий случай: если зашли с шага Салона, дополнительно проверяем прямую связь ManyToMany
        if 'salon' in user_data:
            qs = qs.filter(salons__id=user_data['salon'])
            
        return list(qs.distinct())
        
    masters = await sync_to_async(query_masters)()
    builder = InlineKeyboardBuilder()
    
    for m in masters:
        builder.button(text=m.full_name, callback_data=MasterCallback(id=m.id).pack())
        
    builder.button(text="⬅️ Назад", callback_data="step_back")
    builder.adjust(1)

    if not masters:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Начать сначала", callback_data="back_to_main")
        await message.edit_text(
            "❌ К сожалению, на выбранные параметры сейчас нет свободных специалистов.\n"
            "Попробуйте изменить салон или услугу.", 
            reply_markup=builder.as_markup()
        )
        return
    
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
# ФУНКЦИИ ДЛЯ РАБОТЫ С ПРОМОКОДАМИ
# ==========================================

async def calculate_price_with_discount(service_id: int, promo_code: str = None):
    """Рассчитывает цену с учетом промокода"""

    def get_service_and_promo():
        service = Service.objects.get(id=service_id)
        result = {
            'original_price': float(service.price),
            'discounted_price': float(service.price),
            'promo_code': None,
            'discount_amount': 0,
            'discount_percent': 0,
        }

        if promo_code:
            try:
                promo = PromoCode.objects.get(code=promo_code.upper())

                # Проверяем, активен ли промокод
                if not promo.is_valid():
                    return {**result, 'error': 'Промокод неактивен или истек срок действия'}

                # Проверяем, применяется ли к этой услуге
                if promo.services.exists() and not promo.services.filter(id=service_id).exists():
                    return {**result, 'error': 'Промокод не применяется к этой услуге'}

                # Рассчитываем скидку
                original = float(service.price)
                discounted = promo.apply_discount(original)
                discount_amount = original - discounted
                discount_percent = (discount_amount / original * 100) if original > 0 else 0

                # Формируем результат
                result['discounted_price'] = discounted
                result['promo_code'] = promo.code
                result['discount_amount'] = discount_amount
                result['discount_percent'] = discount_percent

            except PromoCode.DoesNotExist:
                return {**result, 'error': 'Промокод не найден'}

        return result

    return await sync_to_async(get_service_and_promo)()


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

            # Получаем промокод из состояния
            promo_code = user_data.get('promo_code')
            discount_amount = 0

            if promo_code:
                # Рассчитываем скидку (синхронно, без await)
                try:
                    service = Service.objects.get(id=user_data['service'])
                    promo = PromoCode.objects.get(code=promo_code.upper())
                    if promo.is_valid():
                        original_price = float(service.price)
                        discounted_price = promo.apply_discount(original_price)
                        discount_amount = original_price - discounted_price
                except (Service.DoesNotExist, PromoCode.DoesNotExist):
                    discount_amount = 0

            return Appointment.objects.create(
                client=client,
                slot=slot,
                service_id=user_data['service'],
                status='pending',
                promo_code_used=promo_code,  # Сохраняем промокод
                discount_applied=discount_amount  # Сохраняем сумму скидки
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
    original_price = await sync_to_async(lambda: appointment.service.price)()

    # Проверяем промокод и рассчитываем цену со скидкой
    user_data = await state.get_data()
    promo_code = user_data.get('promo_code')
    price_info = await calculate_price_with_discount(appointment.service.id, promo_code)
    final_price = price_info['discounted_price']

    # Формируем строку с ценой и скидкой
    price_text = f"💰 *Сумма:* {int(final_price)} руб."
    if promo_code and price_info.get('promo_code'):
        price_text += f"\n   *Было:* {int(original_price)} руб."
        price_text += f"\n   *Скидка:* -{int(price_info['discount_amount'])} руб. ({int(price_info['discount_percent'])}%)"
        price_text += f"\n   *Промокод:* {promo_code} ✅"

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
        f"{price_text}\n\n"
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
        elif flow == "master":
            from bot_manager.handlers.start import show_main_menu
            await state.clear()
            await callback.message.delete()
            await show_main_menu(callback.message, state, callback.from_user.first_name)
            await callback.answer()
            return

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
        elif flow == "salon":
            from bot_manager.handlers.start import show_main_menu
            await state.clear()
            await callback.message.delete()
            await show_main_menu(callback.message, state, callback.from_user.first_name)
            await callback.answer()
            return

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
# ОБРАБОТЧИКИ ПРОМОКОДОВ
# ================================================================

@booking_router.callback_query(F.data == "enter_promo_from_services")
async def process_enter_promo_from_services(callback: types.CallbackQuery, state: FSMContext):
    """Клиент нажал 'Ввести промокод' на этапе выбора услуги"""
    # Создаем клавиатуру с кнопкой "Пропустить"
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Пропустить", callback_data="skip_promo_from_services")
    builder.adjust(1)

    await callback.message.edit_text(
        "🎫 Введите промокод:\n\n"
        "Примеры: KID20, BIRTHDAY, MAN10",
        reply_markup=builder.as_markup()
    )
    await callback.answer()
    await state.set_state(BookingProcess.entering_promo)


@booking_router.callback_query(F.data == "skip_promo_from_services")
async def process_skip_promo_from_services(callback: types.CallbackQuery, state: FSMContext):
    """Клиент пропустил ввод промокода"""
    await show_service_selection(callback.message, state)
    await callback.answer()


@booking_router.callback_query(F.data == "change_promo")
async def process_change_promo(callback: types.CallbackQuery, state: FSMContext):
    """Клиент хочет изменить или удалить промокод"""
    # Очищаем промокод
    await state.update_data(promo_code=None)

    builder = InlineKeyboardBuilder()
    builder.button(text="🎫 Ввести другой промокод", callback_data="enter_promo_from_services")
    builder.button(text="❌ Пропустить", callback_data="skip_promo_from_services")
    builder.adjust(1)

    await callback.message.edit_text(
        "🔄 Промокод удален.\n\n"
        "Хотите ввести другой промокод или продолжить без скидки?",
        reply_markup=builder.as_markup()
    )

    await state.set_state(BookingProcess.entering_promo)

    await callback.answer()


@booking_router.message(F.text, BookingProcess.entering_promo)
async def process_promo_code(message: types.Message, state: FSMContext):
    """Обработка введенного промокода"""
    promo_code = message.text.strip().upper()

    def check_promo():
        try:
            promo = PromoCode.objects.get(code=promo_code)
            if not promo.is_valid():
                return {'error': 'Промокод неактивен или истек срок действия'}
            return {'promo': promo, 'code': promo_code}
        except PromoCode.DoesNotExist:
            return {'error': 'Промокод не найден'}

    result = await sync_to_async(check_promo)()

    if 'error' in result:
        # Промокод недействителен - предлагаем попробовать снова или пропустить
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Попробовать снова", callback_data="enter_promo_from_services")
        builder.button(text="❌ Пропустить", callback_data="skip_promo_from_services")
        builder.adjust(1)

        await message.answer(
            f"❌ {result['error']}\n\n"
            f"Попробуйте ввести другой промокод или нажмите 'Пропустить'.",
            reply_markup=builder.as_markup()
        )
        return

    # Промокод действителен - сохраняем его
    await state.update_data(promo_code=result['code'])

    # Получаем информацию о скидке
    def get_promo_info():
        promo = PromoCode.objects.get(code=result['code'])
        return {
            'discount_value': float(promo.discount_value),
            'discount_type': promo.discount_type,
            'description': promo.description or ''
        }

    promo_info = await sync_to_async(get_promo_info)()

    # Показываем сообщение об успешном применении
    discount_text = f"{int(promo_info['discount_value'])}%" if promo_info[
                                                                   'discount_type'] == 'percent' else f"{int(promo_info['discount_value'])} руб."

    await message.answer(
        f"✅ Промокод *{result['code']}* применен!\n\n"
        f"🎁 Скидка: {discount_text}\n"
        f"{promo_info['description']}\n\n"
        f"Теперь выберите услугу со скидкой.",
        parse_mode="Markdown"
    )

    # Показываем услуги с обновленными ценами
    await show_service_selection(message, state)


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

            # Получаем данные для карточки
            salon_name = await sync_to_async(lambda: appointment.slot.salon.name)()
            master_name = await sync_to_async(lambda: appointment.slot.master.full_name)()
            service_name = await sync_to_async(lambda: appointment.service.name)()
            slot_date = await sync_to_async(lambda: appointment.slot.date)()
            slot_time = await sync_to_async(lambda: appointment.slot.time)()
            original_price = await sync_to_async(lambda: appointment.service.price)()

            # Получаем промокод из записи
            promo_code = appointment.promo_code_used
            discount_amount = float(appointment.discount_applied or 0)

            # Рассчитываем финальную цену
            final_price = float(original_price) - discount_amount

            # Формируем строку с ценой
            price_text = f"💰 *Сумма:* {int(final_price)} руб."
            if promo_code and discount_amount > 0:
                price_text += f"\n   *Было:* {int(original_price)} руб."
                price_text += f"\n   *Скидка:* -{int(discount_amount)} руб."
                price_text += f"\n   *Промокод:* {promo_code} ✅"

            # ===== СОЗДАЕМ КЛАВИАТУРУ С 3 КНОПКАМИ =====
            action_builder = InlineKeyboardBuilder()
            action_builder.button(
                text="✍️ Оставить отзыв",
                callback_data=f"leave_feedback_{appointment.id}"
            )
            action_builder.button(
                text="💳 Оплатить",
                callback_data=f"pay_appointment_{appointment.id}"
            )
            action_builder.adjust(1)

            # Отправляем сообщение с благодарностью и карточкой записи + 3 кнопки
            await message.answer(
                f"✅ Спасибо за ваш отзыв! Мы ценим ваше мнение.\n\n"
                f"🎉 *Запись успешно оформлена!*\n\n"
                f"📍 *Салон:* {salon_name}\n"
                f"💇 *Процедура:* {service_name}\n"
                f"👤 *Специалист:* {master_name}\n"
                f"{price_text}\n"
                f"⏰ *Время визита:* {slot_date.strftime('%d.%m.%Y')} в {slot_time.strftime('%H:%M')}\n\n"
                f"Выберите действие:",
                reply_markup=action_builder.as_markup(),
                parse_mode="Markdown"
            )

        except Appointment.DoesNotExist:
            await message.answer("❌ Запись не найдена. Возможно, она уже удалена.")
    else:
        # Проверяем, не вводит ли клиент промокод
        current_state = await state.get_state()
        if current_state == BookingProcess.entering_promo:
            return
        await message.answer("Спасибо за сообщение! Если это отзыв, вы можете оставить его в любое время.")
