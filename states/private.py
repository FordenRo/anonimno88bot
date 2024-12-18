from aiogram.fsm.state import State, StatesGroup


class PrivateStates(StatesGroup):
    message = State()
    user = State()
