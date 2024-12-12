from aiogram.fsm.state import StatesGroup, State


class PrivateStates(StatesGroup):
	message = State()
	user = State()

