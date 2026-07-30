from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
from asgiref.sync import sync_to_async
from django.utils import timezone

from bot_manager.models import Client
from bot_manager.handlers.states_utils import BookingProcess, FlowCallback

start_router = Router()

# Функция отрисовки главного меню (вынесли отдельно, чтобы вызывать из двух мест)
async def show_main_menu(message: types.Message, state: FSMContext, user_first_name: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="📍 1. Выбрать ближайший салон", callback_data=FlowCallback(name="salon").pack())
    builder.button(text="⭐ 2. Записаться к любимому мастеру", callback_data=FlowCallback(name="master").pack())
    builder.button(text="💇 3. Выбрать процедуру", callback_data=FlowCallback(name="service").pack())
    builder.button(text="📞 4. Хочу записаться по телефону", callback_data=FlowCallback(name="phone").pack())
    builder.adjust(1)
    
    await message.answer(
        f"Здравствуйте, {user_first_name}! Вас приветствует сеть салонов красоты Ольги.\n"
        f"Как бы вы хотели оформить запись?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BookingProcess.choosing_flow)


@start_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    # Регистрация / получение клиента из БД Django
    client, _ = await sync_to_async(Client.objects.get_or_create)(
        telegram_id=message.from_user.id,
        defaults={'username': message.from_user.username or ""}
    )
    
    # ПРОВЕРКА ЮРИДИЧЕСКОГО БЛОКА
    if not client.is_terms_accepted:
        builder = InlineKeyboardBuilder()
        builder.button(text="📄 Читать соглашение", callback_data="view_terms")
        builder.button(text="✅ Принять и продолжить", callback_data="accept_terms")
        builder.adjust(1)
        
        await message.answer(
            "Добро пожаловать!\n\nДля продолжения работы с ботом, пожалуйста, "
            "ознакомьтесь с Политикой обработки персональных данных (ФЗ-152).\n"
            "Нажимая кнопку ниже, вы даете согласие на обработку данных.",
            reply_markup=builder.as_markup()
        )
        return  # Прерываем выполнение, меню флоу НЕ показываем
        
    # Если клиент уже принимал соглашение ранее, сразу показываем главное меню
    await show_main_menu(message, state, message.from_user.first_name)

@start_router.callback_query(F.data == "view_terms")
async def handle_view_terms(callback: types.CallbackQuery):
    # Укажите точный локальный путь к файлу соглашения на вашем сервере
    pdf_path = "media/documents/terms.pdf" 
    
    try:
        # Создаем объект файла для aiogram 3.x
        document = FSInputFile(path=pdf_path, filename="terms.pdf")
        
        # Отправляем документ пользователю
        await callback.message.answer_document(
            document=document,
            caption="Ознакомьтесь с полным текстом соглашения об обработке персональных данных."
        )
        # Гасим часики на инлайн-кнопке
        await callback.answer()
    except Exception as e:
        # На случай, если файл удалили или путь указан неверно
        await callback.answer("Ошибка при загрузке файла. Обратитесь в поддержку.", show_alert=True)


# ОБРАБОТЧИК НАЖАТИЙ НА КНОПКУ «ПРИНЯТЬ СОГЛАШЕНИЕ»
@start_router.callback_query(F.data == "accept_terms")
async def handle_accept_terms(callback: types.CallbackQuery, state: FSMContext):
    # Обновляем флаг согласия и пишем текущую дату/время в базу данных Django
    def update_client_terms():
        try:
            client = Client.objects.get(telegram_id=callback.from_user.id)
            client.is_terms_accepted = True
            client.terms_accepted_at = timezone.now()  # Записываем точное время принятия
            client.save()
            return True
        except Client.DoesNotExist:
            return False

    await sync_to_async(update_client_terms)()
    
    # Удаляем сообщение с офертой, чтобы не засорять историю
    await callback.message.delete()
    
    # Показываем главное меню
    await show_main_menu(callback.message, state, callback.from_user.first_name)
    await callback.answer("Спасибо! Согласие принято.")


@start_router.callback_query(FlowCallback.filter(), BookingProcess.choosing_flow)
async def handle_flow_selection(callback: types.CallbackQuery, callback_data: FlowCallback, state: FSMContext):
    flow = callback_data.name
    await state.update_data(flow=flow)
    
    # СЦЕНАРИЙ 4: ЗАПИСЬ ПО ТЕЛЕФОНУ
    if flow == "phone":
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад в меню", callback_data="back_to_main")
        builder.adjust(1)

        await callback.message.edit_text(
            "📞 *Запись по телефону*\n\n"
            "Вы можете связаться с нашим администратором напрямую.\n"
            "Он поможет подобрать удобное время и ответит на любые вопросы.\n\n"
            "Тапните по номеру ниже, чтобы скопировать его и позвонить:\n"
            "👉 `+74951112233`\n\n"  # Текст в обратных кавычках станет моноширинным
            "⏰ Наш администратор на связи ежедневно с 09:00 до 21:00.",
            parse_mode="Markdown", 
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    from bot_manager.handlers.booking import show_salon_selection, show_master_selection, show_service_selection

    if flow == "salon":
        await show_salon_selection(callback.message, state)
    elif flow == "master":
        await show_master_selection(callback.message, state)
    elif flow == "service":
        await show_service_selection(callback.message, state)
        
    await callback.answer()

