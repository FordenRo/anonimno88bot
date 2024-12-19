from aiogram.fsm.state import State, StatesGroup


class MuteStates(StatesGroup):
    user = State()
    duration = State()
    reason = State()
