from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

from .keyboards import remove_keyboard, start_menu_keyboard
from .tip_handlers import start_tip_flow

router = Router()
router.callback_query.middleware(CallbackAnswerMiddleware())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    await state.clear()
    payload = command.args or ""
    if payload.startswith("tip_"):
        await start_tip_flow(message, state, payload[4:])
        return
    await message.answer(
        "Здравствуйте! Это бот записи в салон красоты.\nКак удобнее записаться?",
        reply_markup=start_menu_keyboard(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Запись отменена. Начнём заново — /start",
        reply_markup=remove_keyboard(),
    )


@router.callback_query(StateFilter("*"), F.data == "to_menu")
async def on_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Здравствуйте! Это бот записи в салон красоты.\nКак удобнее записаться?",
        reply_markup=start_menu_keyboard(),
    )


@router.callback_query(F.data == "exit")
async def on_exit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("До встречи! Вернуться в меню — /start")
