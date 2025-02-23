import time
from asyncio import create_task

from aiogram import Router, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from sqlalchemy import select

from database import FakeMessage, Opportunity, RealMessage, User, DeleteInfo
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

    reply_to = getattr(session.scalar(select(FakeMessage).where(FakeMessage.id == message.reply_to_message.message_id)),
                       'real_message',
                       session.scalar(select(RealMessage).where(RealMessage.id == message.reply_to_message.message_id)))
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

    delete_info = DeleteInfo(real_message=reply_to, user=user, time=current_time)
    session.add(delete_info)
    session.commit()

    for fake_message in reply_to.fake_messages:
        if fake_message.user.has_opportunity(Opportunity.CAN_SEE_DELETED_MESSAGES):
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text='Удаленное', callback_data=f'delinfo {delete_info.id}')]])
            create_task(bot.edit_message_reply_markup(message_id=fake_message.id, chat_id=fake_message.user_id,
                                                      reply_markup=keyboard))
            continue

        create_task(bot.delete_message(fake_message.user_id, fake_message.id))


@router.callback_query(F.data.split()[0] == 'delinfo')
async def callback(callback: CallbackQuery):
    id = int(callback.data.split()[1])

    delete_info = session.scalar(select(DeleteInfo).where(DeleteInfo.id == id))
    if not delete_info:
        await callback.answer('Ошибка')
        return

    await callback.answer(f'Удалил {delete_info.user.role} №{delete_info.user.fake_id}\n'
                          f'{time_to_str(int(time.time()) - delete_info.time)} назад', True)
