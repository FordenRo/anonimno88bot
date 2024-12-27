from aiogram.fsm.state import State, StatesGroup


class PollStates(StatesGroup):
    description = State()
    variant = State()
    more = State()
    duration = State()
