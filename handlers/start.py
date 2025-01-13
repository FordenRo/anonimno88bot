import os.path
import time
from asyncio import create_task, gather

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message
from sqlalchemy import exists, select

from database import CommandOpportunity, Opportunity, Role, User
from globals import bot, notif_bot, session
from handlers import warn
from utils import get_section, get_unique_user_fake_id, text_inline_markup, update_user_commands

router = Router()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if session.query(exists(User).where(User.id == message.from_user.id)).scalar():
        user = session.scalar(select(User).where(User.id == message.from_user.id))

        args = message.text.split()
        if len(args) > 1:
            args = args[1].split('-')
            if args[0] == 'warn':
                if not user.has_command_opportunity(CommandOpportunity.warn):
                    return

                id = int(args[1])
                await warn.handle_user_state(user=user, state=state, target_id=id)
    else:
        user = User(id=message.from_user.id, fake_id=get_unique_user_fake_id(), joined_time=int(time.time()))
        session.add(user)
        session.commit()

        if user.id == 7625373673:
            user.role = Role.OWNER

        await bot.send_animation(user.id,
                                 FSInputFile(get_section('welcome/animation'),
                                             os.path.basename(get_section('welcome/animation'))),
                                 caption=get_section('welcome/message'),
                                 reply_markup=text_inline_markup(get_section('welcome/buttons')))
        create_task(new_user_notification(user))
    await message.delete()
    await update_user_commands(user)


async def new_user_notification(user: User):
    tasks = []
    for target in session.scalars(select(User).where(User.id != user.id)):
        if target.has_opportunity(Opportunity.CAN_RECEIVE_USER_JOINED_BANNED_MESSAGE):
            chat = await bot.get_chat(user.id)
            tasks += [notif_bot.send_message(target.id,
                                             f'Новый {user.role} №{user.fake_id} {chat.full_name} '
                                             f'({f'@{chat.username}' if chat.username else f'id_{user.id}'})')]
    await gather(*tasks)
