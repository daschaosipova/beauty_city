from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.callback_data import CallbackData

# Состояния FSM для пошагового сценария записи
class BookingProcess(StatesGroup):
    choosing_flow = State()      # Главное меню выбора флоу
    step_salon = State()         # Шаг: Выбор салона
    step_service = State()       # Шаг: Выбор процедуры (и просмотр цен)
    step_master = State()        # Шаг: Выбор мастера
    step_date_time = State()     # Шаг: Выбор даты и времени (слота)
    entering_phone = State()     # Шаг: Ввод контактов

# Фабрики кнопок для обработки колбэков
class FlowCallback(CallbackData, prefix="flow"):
    name: str  # 'salon', 'master', 'service', 'phone'

class SalonCallback(CallbackData, prefix="sal"):
    id: int

class ServiceCallback(CallbackData, prefix="ser"):
    id: int

class MasterCallback(CallbackData, prefix="mas"):
    id: int

class SlotCallback(CallbackData, prefix="slo"):
    id: int
