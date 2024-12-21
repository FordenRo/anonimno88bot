from aiogram.fsm.state import State, StatesGroup


class UserProfileStates(StatesGroup):
    user = State()
    set_role = State()
