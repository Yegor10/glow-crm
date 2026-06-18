"""FSM-стани для діалогів бота."""
from aiogram.fsm.state import State, StatesGroup


class BookingFlow(StatesGroup):
    service = State()
    date = State()
    time = State()
    note = State()


class ProfileFlow(StatesGroup):
    phone = State()


class AdminService(StatesGroup):
    name = State()
    price = State()
    duration = State()
    emoji = State()


class AdminSchedule(StatesGroup):
    work_start = State()
    work_end = State()
    slot_step = State()
    horizon = State()


class AdminBroadcast(StatesGroup):
    text = State()


class AdminWelcome(StatesGroup):
    text = State()


class AdminAddAdmin(StatesGroup):
    username = State()
