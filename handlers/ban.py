import time
from asyncio import create_task, gather, sleep

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from database import Ban, CommandOpportunity, User
from filters.command import UserCommand
from filters.user import BannedUserFilter, UserFilter
from globals import bot, logger, session
from handlers.delayed import DelayedMessage
from states.ban import BanStates
from utils import cancel_markup, get_section, time_to_str

router = Router()


@router.message(BannedUserFilter())
async def message(message: Message, user: User, ban: Ban):
    await message.delete()
    DelayedMessage(
        await bot.send_message(user.id, get_section('ban/user/banned')
                               .format(ban, remaining_time=time_to_str(ban.time + ban.duration - int(time.time())))),
        2).start()


@router.message(UserCommand('ban', description='Выдать бан', opportunity=CommandOpportunity.ban))
async def command(message: Message, user: User, state: FSMContext):
    await message.delete()
    msg = await bot.send_message(user.id, get_section('ban/command/user'), reply_markup=cancel_markup)
    await state.set_state(BanStates.user)
    await state.set_data({'message': msg})


@router.message(BanStates.user, UserFilter())
async def user_state(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()

    try:
        target_id = int(message.text)
    except ValueError:
        DelayedMessage(await bot.send_message(user.id, get_section('ban/command/error/value')), 2).start()
        await state.clear()
        return

    target = session.scalar(select(User).where(User.fake_id == target_id))
    if not target:
        DelayedMessage(await bot.send_message(user.id, get_section('ban/command/error/user')), 2).start()
        await state.clear()
        return

    if target.ban:
        DelayedMessage(await bot.send_message(user.id, get_section('ban/command/error/banned')), 2).start()
        await state.clear()
        return

    msg = await bot.send_message(user.id, get_section('ban/command/duration'), reply_markup=cancel_markup)
    await state.set_state(BanStates.duration)
    await state.set_data({'message': msg, 'target_id': target.id})


@router.message(BanStates.duration, UserFilter())
async def duration_state(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()

    try:
        duration = int(float(message.text) * 60)
    except ValueError:
        DelayedMessage(await bot.send_message(user.id, get_section('ban/command/error/duration')), 2).start()
        await state.clear()
        return

    msg = await bot.send_message(user.id, get_section('ban/command/reason'), reply_markup=cancel_markup)
    await state.set_state(BanStates.reason)
    await state.set_data({'message': msg, 'target_id': await state.get_value('target_id'), 'duration': duration})


@router.message(BanStates.reason, UserFilter())
async def reason_state(message: Message, user: User, state: FSMContext):
    sender = user
    await message.delete()
    await (await state.get_value('message')).delete()
    duration = await state.get_value('duration')
    target_id = await state.get_value('target_id')
    target = session.scalar(select(User).where(User.id == target_id))
    await state.clear()

    reason = message.text
    await give_ban(target, sender, duration, reason)


async def give_ban(target: User, sender: User, duration: int, reason: str):
    ban = Ban(user=target, sender=sender, duration=duration, reason=reason, time=time.time())
    session.add(ban)
    session.commit()
    register_ban(ban)

    tasks = [bot.send_message(target.id, get_section('ban/user/receive')
                              .format(ban, remaining_time=time_to_str(ban.duration)))]
    for user in session.scalars(select(User).where(User.id != target.id)).all():
        if user.ban:
            continue

        tasks += [bot.send_message(user.id, get_section('ban/broadcast')
                                   .format(ban, duration=time_to_str(ban.duration)))]
    await gather(*tasks)


def register_ban(ban: Ban):
    async def task(ban: Ban):
        remaining_time = max(ban.time + ban.duration - time.time(), 0)
        await sleep(remaining_time)
        await bot.send_message(ban.user_id, get_section('ban/user/over'))
        if ban not in session:
            return
        logger.debug(f'Ban #{ban.id} is over')
        session.delete(ban)
        session.commit()
        session.refresh(ban.user)

    create_task(task(ban))


def create_ban_tasks():
    for ban in session.scalars(select(Ban)).all():
        register_ban(ban)
