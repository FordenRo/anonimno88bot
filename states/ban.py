from aiogram.fsm.state import State, StatesGroup


class BanStates(StatesGroup):
    user = State()
    duration = State()
    reason = State()
