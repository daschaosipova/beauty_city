from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    salon = State()
    service = State()
    price = State()
    master = State()
    date = State()
    time = State()
    terms = State()
    contact = State()
    confirm = State()


class MasterFirstStates(StatesGroup):
    master = State()
    service = State()
    salon = State()
    date = State()
    time = State()
    terms = State()
    contact = State()
    confirm = State()


class ProcedureFirstStates(StatesGroup):
    service = State()
    date = State()
    time = State()
    master = State()
    salon = State()
    terms = State()
    contact = State()
    confirm = State()


class StaffStates(StatesGroup):
    auth = State()
    salon = State()
    service = State()
    master = State()
    date = State()
    time = State()
    phone = State()
    confirm = State()


class PromoStates(StatesGroup):
    code = State()


class ReviewStates(StatesGroup):
    rating = State()
    text = State()


class TipStates(StatesGroup):
    amount = State()

