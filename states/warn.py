from aiogram.fsm.state import State, StatesGroup


class WarnStates(StatesGroup):
    user = State()
    type = State()
