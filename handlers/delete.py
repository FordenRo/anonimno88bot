import time

from aiogram import Router
from aiogram.types import Message
from sqlalchemy import select

from database import Opportunity, RealMessage, User, FakeMessage
from filters.command import UserCommand
from globals import bot, session
from handlers.delayed import DelayedMessage
from utils import get_section, hide_markup, time_to_str

router = Router()


@router.message(UserCommand('delete', description=get_section('command_description/delete')))
async def command(message: Message, user: User):
    await message.delete()

    current_time = int(time.time())
    debounce = get_section('delete/delay')
    remaining_time = user.last_delete_time + debounce - current_time

    if remaining_time > 0 and not user.has_opportunity(Opportunity.NO_DELETE_RESTRICTIONS):
        DelayedMessage(
            await bot.send_message(user.id, get_section('delete/debounce').format(time_to_str(remaining_time))),
            2).start()
        return

    if not message.reply_to_message:
        DelayedMessage(
            await bot.send_message(user.id, 'Вы должны ответить на сообщение, для использования данной команды.'),
            2).start()
        return

    reply_to = getattr(session.scalar(select(FakeMessage).where(FakeMessage.id == message.reply_to_message.message_id)), 'real_message', session.scalar(select(RealMessage).where(RealMessage.id == message.reply_to_message.message_id)))
    if not reply_to:
        DelayedMessage(await bot.send_message(user.id, get_section('delete/error')), 2).start()
        return

    if reply_to.sender != user and not user.has_opportunity(Opportunity.DELETE_OTHERS_MESSAGES):
        DelayedMessage(await bot.send_message(user.id, get_section('delete/other')), 2).start()
        return

    try:
        await bot.delete_message(reply_to.sender.id, reply_to.id)
    except:
        await bot.send_message(user.id, get_section('delete/error'), reply_markup=hide_markup)
        return

    for fake_message in reply_to.fake_messages:
        try:
            await bot.delete_message(fake_message.user_id, fake_message.id)
        except:
            pass
