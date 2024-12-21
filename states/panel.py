from aiogram.fsm.state import State, StatesGroup


class PanelStates(StatesGroup):
    execute = State()
