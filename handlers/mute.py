import time
from asyncio import create_task, gather, sleep

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from database import CommandOpportunity, Mute, User
from filters.command import UserCommand
from filters.user import MutedUserFilter, UserFilter
from globals import bot, logger, session
from handlers.delayed import DelayedMessage
from states.mute import MuteStates
from utils import cancel_markup, get_section, time_to_str

router = Router()


@router.message(MutedUserFilter())
async def message(message: Message, user: User, mute: Mute):
    await message.delete()
    DelayedMessage(
        await bot.send_message(user.id, get_section('mute/user/muted')
                               .format(mute, remaining_time=time_to_str(mute.time + mute.duration - int(time.time())))),
        2).start()


@router.message(UserCommand('mute', description='Выдать муть', opportunity=CommandOpportunity.mute))
async def command(message: Message, user: User, state: FSMContext):
    await message.delete()
    msg = await bot.send_message(user.id, get_section('mute/command/user'), reply_markup=cancel_markup)
    await state.set_state(MuteStates.user)
    await state.set_data({'message': msg})


@router.message(MuteStates.user, UserFilter())
async def user_state(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()

    try:
        target_id = int(message.text)
    except ValueError:
        DelayedMessage(await bot.send_message(user.id, get_section('mute/command/error/value')), 2).start()
        await state.clear()
        return

    target = session.scalar(select(User).where(User.fake_id == target_id))
    if not target:
        DelayedMessage(await bot.send_message(user.id, get_section('mute/command/error/user')), 2).start()
        await state.clear()
        return

    if target.mute:
        DelayedMessage(await bot.send_message(user.id, get_section('mute/command/error/muted')), 2).start()
        await state.clear()
        return

    msg = await bot.send_message(user.id, get_section('mute/command/duration'), reply_markup=cancel_markup)
    await state.set_state(MuteStates.duration)
    await state.set_data({'message': msg, 'target_id': target.id})


@router.message(MuteStates.duration, UserFilter())
async def duration_state(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()

    try:
        duration = int(float(message.text) * 60)
    except ValueError:
        DelayedMessage(await bot.send_message(user.id, get_section('mute/command/error/duration')), 2).start()
        await state.clear()
        return

    msg = await bot.send_message(user.id, get_section('mute/command/reason'), reply_markup=cancel_markup)
    await state.set_state(MuteStates.reason)
    await state.set_data({'message': msg, 'target_id': await state.get_value('target_id'), 'duration': duration})


@router.message(MuteStates.reason, UserFilter())
async def reason_state(message: Message, user: User, state: FSMContext):
    sender = user
    await message.delete()
    await (await state.get_value('message')).delete()
    duration = await state.get_value('duration')
    target_id = await state.get_value('target_id')
    target = session.scalar(select(User).where(User.id == target_id))
    await state.clear()

    reason = message.text
    mute = Mute(time=time.time(), duration=duration, user=target, sender=sender, reason=reason)
    session.add(mute)
    session.commit()
    register_mute(mute)

    tasks = [bot.send_message(target.id, get_section('mute/user/receive')
                              .format(mute, remaining_time=time_to_str(mute.duration)))]
    for user in session.scalars(select(User).where(User.id != target.id)).all():
        if user.ban:
            continue

        tasks += [bot.send_message(user.id, get_section('mute/broadcast')
                                   .format(mute, duration=time_to_str(mute.duration)))]
    await gather(*tasks)


def register_mute(mute: Mute):
    async def task(mute: Mute):
        remaining_time = max(mute.time + mute.duration - time.time(), 0)
        await sleep(remaining_time)
        await bot.send_message(mute.user_id, get_section('mute/user/over'))
        if mute not in session:
            return
        logger.debug(f'Mute #{mute.id} is over')
        session.delete(mute)
        session.commit()
        session.refresh(mute.user)

    create_task(task(mute))


def create_mute_tasks():
    for mute in session.scalars(select(Mute)).all():
        register_mute(mute)
