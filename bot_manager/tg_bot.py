import os
import sys
import django
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from environs import Env  # Импортируем класс Env для работы с переменными окружения

# =====================================================================
# ИСПРАВЛЕНИЕ ПУТЕЙ (Добавьте эти две строки!)
# =====================================================================
# Берём папку, в которой лежит сам tg_bot.py, находим её родительскую папку (корень проекта)
# и говорим Python искать модули (включая 'core' и 'bot_manager') именно там.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# =====================================================================
# НАСТРОЙКА И ЧТЕНИЕ ПЕРЕМЕННЫХ ИЗ ФАЙЛА .env
# =====================================================================
env = Env()
# Ищем файл .env в корне проекта и загружаем из него данные
env.read_env()

# Считываем токен безопасности. Если в файле .env забыли его указать,
# программа выдаст понятную ошибку, а не просто упадет в процессе работы.
BOT_TOKEN = env.str("BOT_TOKEN")

# =====================================================================
# НАСТРОЙКА СВЯЗИ С DJANGO
# =====================================================================
# Указываем Python, где лежит файл конфигурации нашего Django-проекта
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
# Запускаем внутренние механизмы Django, чтобы таблицы стали доступны для бота
django.setup()

# Теперь импортируем созданные ранее Django-модели (таблицы) базы данных
from bot_manager.models import Client, Salon, Service, Master, TimeSlot

# Создаем объекты самого бота и диспетчера (управляет входящими сообщениями)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =====================================================================
# 1. СЦЕНАРИЙ: Команда /start (Первый визит или перезапуск)
# =====================================================================
# Этот декоратор ловит текстовую команду /start от пользователя
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    telegram_id = message.from_user.id  # Уникальный числовой ID человека в Telegram
    username = message.from_user.username  # Публичное имя пользователя (например, @ivanov)

    # Ищем клиента в базе. Если его там нет — автоматически создаем запись
    # aget_or_create — это специальная безопасная функция Django для работы внутри бота
    client, created = await Client.objects.aget_or_create(
        telegram_id=telegram_id,
        defaults={'username': username}
    )

    # Проверяем юридический блок: дал ли клиент согласие на обработку данных?
    if not client.is_terms_accepted:
        # Если согласия нет — создаем кнопку под текстом
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Принять и продолжить", callback_data="accept_terms")

        # Отправляем сообщение с правилами и прикрепляем кнопку
        await message.answer(
            "Добро пожаловать!\n\nДля продолжения работы с ботом, пожалуйста, "
            "ознакомьтесь с Политикой обработки персональных данных (ФЗ-152).\n"
            "Нажимая кнопку ниже, вы даете согласие на обработку данных.",
            reply_markup=builder.as_markup()
        )
    else:
        # Если клиент уже принимал соглашение ранее, сразу показываем меню салонов
        await show_salons_menu(message)


# =====================================================================
# 2. СЦЕНАРИЙ: Клиент принял условия (Нажал кнопку "Принять и продолжить")
# =====================================================================
# Фильтр F.data == "accept_terms" проверяет, что нажата именно кнопка согласия
@dp.callback_query(F.data == "accept_terms")
async def process_accept_terms(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id

    # Находим нашего клиента в базе данных Django по его ID
    client = await Client.objects.aget(telegram_id=telegram_id)
    # Меняем статус согласия на "Да"
    client.is_terms_accepted = True

    # Импортируем инструмент времени Django и сохраняем точную дату согласия
    from django.utils import timezone
    client.terms_accepted_at = timezone.now()

    # Асинхронно сохраняем обновленную карточку клиента в базу данных
    await client.asave()

    # Показываем короткое всплывающее уведомление сверху экрана в Telegram
    await callback.answer("Спасибо! Юридическое согласие зафиксировано.")
    # Переводим пользователя к следующему шагу — выбору салона
    await show_salons_menu(callback.message)


# =====================================================================
# СЛУЖЕБНАЯ ФУНКЦИЯ: Показ списка салонов (Используется в нескольких сценариях)
# =====================================================================
async def show_salons_menu(message: types.Message):
    # Конструктор для создания инлайн-кнопок прямо под сообщением
    builder = InlineKeyboardBuilder()

    # Перебираем все салоны, которые вы добавили через админку Django
    async for salon in Salon.objects.all():
        builder.button(
            text=f"📍 {salon.name}", 
            # Зашиваем ID салона в кнопку (например: "select_salon_3")
            # Это поможет боту понять, на какой именно салон нажал клиент
            callback_data=f"select_salon_{salon.id}"
        )

    # Размещаем кнопки строго по одной штуке в ряд (чтобы текст не обрезался)
    builder.adjust(1)

    # Отправляем сообщение со сформированными кнопками салонов
    await message.answer(
        "Выберите удобный для вас филиал нашей сети:",
        reply_markup=builder.as_markup()
    )


# =====================================================================
# 3. СЦЕНАРИЙ: Клиент выбрал салон -> Показываем список услуг и цены
# =====================================================================
# Фильтр ловит любое нажатие кнопки, текст которой начинается с "select_salon_"
@dp.callback_query(F.data.startswith("select_salon_"))
async def process_salon_selection(callback: types.CallbackQuery):
    # Вытаскиваем ID салона (удаляем текстовый префикс "select_salon_")
    # Из "select_salon_5" мы получим число 5
    salon_id = int(callback.data.replace("select_salon_", ""))

    # Делаем запрос к базе и находим выбранный салон по его ID
    salon = await Salon.objects.aget(id=salon_id)

    # Создаем новый набор кнопок для вывода процедур
    builder = InlineKeyboardBuilder()

    # Загружаем из Django абсолютно все услуги и цены, которые есть в базе
    async for service in Service.objects.all():
        builder.button(
            text=f"💇‍♀️ {service.name} ({int(service.price)} руб.)",
            # Зашиваем ID услуги в кнопку, чтобы обработать на следующем шаге
            callback_data=f"select_service_{service.id}"
        )

    # Выстраиваем кнопки процедур в один столбец
    builder.adjust(1)

    # Показываем быстрый пуш сверху экрана: "Выбран: Салон на Тверской"
    await callback.answer(f"Выбран: {salon.name}")

    # Красиво обновляем старое сообщение бота: меняем текст и ставим новые кнопки услуг
    await callback.message.edit_text(
        text=f"Вы выбрали филиал: **{salon.name}**\n\nТеперь выберите необходимую процедуру из нашего прайса:",
        parse_mode="Markdown",  # Позволяет делать текст жирным с помощью звездочек **
        reply_markup=builder.as_markup()
    )


# =====================================================================
# 4. СЦЕНАРИЙ: Клиент выбрал услугу -> Показываем мастеров, которые её делают
# =====================================================================
# Фильтр ловит нажатие кнопки, которая начинается на "select_service_"
@dp.callback_query(F.data.startswith("select_service_"))
async def process_service_selection(callback: types.CallbackQuery):
    # Достаем ID выбранной услуги из даты кнопки (например, из "select_service_2" получим число 2)
    service_id = int(callback.data.replace("select_service_", ""))
    
    # Находим эту услугу в базе данных Django
    service = await Service.objects.aget(id=service_id)
    
    # Создаем конструктор кнопок для мастеров
    builder = InlineKeyboardBuilder()
    
    # ВАЖНО: Мы фильтруем мастеров! Достаем из базы ТОЛЬКО ТЕХ,
    # у кого в списке услуг (services) привязана именно эта процедура,
    # и кто сейчас активно работает (is_active=True).
    async for master in Master.objects.filter(services__id=service_id, is_active=True):
        builder.button(
            text=f"👤 Мастер: {master.full_name}",
            # Зашиваем в кнопку ID услуги и ID мастера, чтобы не потерять контекст
            callback_data=f"select_master_{master.id}_srv_{service_id}"
        )
        
    builder.adjust(1)
    
    # Показываем пуш сверху экрана
    await callback.answer(f"Выбрана услуга: {service.name}")
    
    # Обновляем сообщение: выводим список подходящих специалистов
    await callback.message.edit_text(
        text=f"Вы выбрали услугу: **{service.name}**\n\nПожалуйста, выберите специалиста для записи:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )


# =====================================================================
# 5. СЦЕНАРИЙ: Клиент выбрал мастера -> Показываем доступные ДАТЫ
# =====================================================================
# Фильтр ловит кнопку формата: select_master_[ID]_srv_[ID]
@dp.callback_query(F.data.startswith("select_master_"))
async def process_master_selection(callback: types.CallbackQuery):
    # Разбираем callback_data на части, чтобы узнать ID мастера и услуги
    # Текст "select_master_1_srv_2" превратится в список: ['', '1', 'srv', '2']
    data_parts = callback.data.split("_")
    master_id = int(data_parts[2])
    service_id = int(data_parts[4])
    
    master = await Master.objects.aget(id=master_id)
    
    # Ищем в базе уникальные даты, в которые у этого мастера есть СВОБОДНЫЕ (не занятые) слоты
    # order_by('date') отсортирует дни от ближайшего к будущим
    # distinct('date') уберет дубликаты, чтобы одна дата не повторялась много раз
    dates = []
    async for slot in TimeSlot.objects.filter(master_id=master_id, is_booked=False).order_by('date'):
        if slot.date not in dates:
            dates.append(slot.date)
            
    builder = InlineKeyboardBuilder()
    
    # Создаем кнопки для каждой уникальной даты
    for date in dates:
        # Переводим дату в красивый формат для человека (например: "28.07.2026")
        nice_date = date.strftime("%d.%m.%Y")
        # В кнопку зашиваем: ID мастера, ID услуги и саму дату через дефис (ГГГГ-ММ-ДД)
        builder.button(
            text=f"📅 {nice_date}",
            callback_data=f"date_{date}_m_{master_id}_s_{service_id}"
        )
        
    builder.adjust(2) # Выводим даты красиво — по 2 штуки в ряд
    
    await callback.answer(f"Выбран мастер: {master.full_name}")
    
    await callback.message.edit_text(
        text=f"Вы выбрали мастера: **{master.full_name}**\n\nПожалуйста, выберите подходящую дату для визита:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )


# =====================================================================
# 6. СЦЕНАРИЙ: Клиент выбрал дату -> Показываем доступное ВРЕМЯ (слоты)
# =====================================================================
# Фильтр ловит кнопку, которая начинается с "date_"
@dp.callback_query(F.data.startswith("date_"))
async def process_date_selection(callback: types.CallbackQuery):
    # Разбираем данные из кнопки (например: "date_2026-07-28_m_1_s_2")
    data_parts = callback.data.split("_")
    selected_date = data_parts[1] # Строка с датой
    master_id = int(data_parts[3])
    service_id = int(data_parts[5])
    
    builder = InlineKeyboardBuilder()
    
    # Ищем в базе конкретные свободные слоты времени именно на эту дату к этому мастеру
    # Сортируем по времени (от раннего к позднему)
    async for slot in TimeSlot.objects.filter(
        master_id=master_id, 
        date=selected_date, 
        is_booked=False
    ).order_by('time'):
        # Форматируем время в привычный вид "ЧЧ:ММ" (например: "14:30")
        nice_time = slot.time.strftime("%H:%M")
        # Передаем ID слота и ID услуги на финальный шаг — подтверждение и запрос телефона
        builder.button(
            text=f"⏰ {nice_time}",
            callback_data=f"book_slot_{slot.id}_srv_{service_id}"
        )
        
    builder.adjust(4) # Время короткое, поэтому выводим по 4 кнопки в ряд (сеткой)
    
    # Форматируем дату для заголовка сообщения
    from datetime import datetime
    date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
    nice_date_str = date_obj.strftime("%d.%m.%Y")
    
    await callback.answer()
    await callback.message.edit_text(
        text=f"Доступные слоты времени на **{nice_date_str}**:\n\nВыберите удобное время для записи:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )


# =====================================================================
# ЗАПУСК БОТА (Вечный цикл прослушивания Telegram)
# =====================================================================
async def main():
    print("Бот успешно запущен и подключен к Django через фильтры 'F'!")
    # Запуск поллинга — бот начинает постоянно спрашивать сервера Telegram о новых сообщениях
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Запуск главной асинхронной функции
    asyncio.run(main())
