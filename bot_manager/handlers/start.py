from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async

from bot_manager.models import Client
from bot_manager.handlers.states_utils import BookingProcess, FlowCallback

start_router = Router()

@start_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    # Регистрация клиента в БД Django
    client, _ = await sync_to_async(Client.objects.get_or_create)(
        telegram_id=message.from_user.id,
        defaults={'username': message.from_user.username or ""}
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📍 1. Выбрать ближайший салон", callback_data=FlowCallback(name="salon").pack())
    builder.button(text="⭐ 2. Записаться к любимому мастеру", callback_data=FlowCallback(name="master").pack())
    builder.button(text="💇 3. Выбрать процедуру", callback_data=FlowCallback(name="service").pack())
    builder.button(text="📞 4. Хочу записаться по телефону", callback_data=FlowCallback(name="phone").pack())
    builder.adjust(1)
    
    await message.answer(
        f"Здравствуйте, {message.from_user.first_name}! Вас приветствует сеть салонов красоты Ольги.\n"
        f"Как бы вы хотели оформить запись?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BookingProcess.choosing_flow)

@start_router.callback_query(FlowCallback.filter(), BookingProcess.choosing_flow)
async def handle_flow_selection(callback: types.CallbackQuery, callback_data: FlowCallback, state: FSMContext):
    flow = callback_data.name
    await state.update_data(flow=flow)
    
    # СЦЕНАРИЙ 4: ЗАПИСЬ ПО ТЕЛЕФОНУ
    if flow == "phone":
        await callback.message.edit_text(
            "📞 Вы можете записаться напрямую через нашего администратора.\n\n"
            "Нажмите на номер телефона ниже, чтобы совершить звонок:\n"
            "👉 +7 (495) 111-22-33\n\n"
            "Или введите /start, чтобы вернуться к автоматической записи."
        )
        await state.clear()
        return

    # Импортируем функции динамически для предотвращения круговых импортов
    from bot_manager.handlers.booking import show_salon_selection, show_master_selection, show_service_selection

    if flow == "salon":
        await show_salon_selection(callback.message, state)
    elif flow == "master":
        await show_master_selection(callback.message, state)
    elif flow == "service":
        await show_service_selection(callback.message, state)
        
    await callback.answer()
