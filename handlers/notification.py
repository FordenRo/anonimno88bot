from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from database import Opportunity, User
from filters.user import UserFilter
from globals import notif_bot

router = Router()


@router.message(CommandStart(), UserFilter())
async def start(message: Message, user: User):
    if not user.has_opportunity(Opportunity.NOTIFICATION):
        return

    await message.delete()
    await notif_bot.send_message(user.id, 'Теперь вы будете получать оповещения тут')
