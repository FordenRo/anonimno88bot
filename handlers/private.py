from aiogram import Router
from aiogram.types import Message

from database import bot, session
from filters.user import UserFilter
from states.private import PrivateStates

router = Router()


@router.message(UserFilter(), PrivateStates.message)
async def message(message: Message):
	pass

