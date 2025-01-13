import time
from asyncio import create_task, gather, sleep

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy import select

from database import CommandOpportunity, User, Warn
from filters.command import UserCommand
from filters.user import UserFilter
from globals import bot, logger, session
from handlers.ban import give_ban
from handlers.delayed import DelayedMessage
from handlers.mute import give_mute
from states.warn import WarnStates
from utils import cancel_markup, get_section, time_to_str

router = Router()


@router.message(UserCommand('warn', description=get_section('command_description/warn'),
                            opportunity=CommandOpportunity.warn))
async def command(message: Message, user: User, state: FSMContext):
    await message.delete()
    msg = await bot.send_message(user.id, get_section('warn/command/user'), reply_markup=cancel_markup)
    await state.set_state(WarnStates.user)
    await state.set_data({'message': msg})


@router.message(WarnStates.user, UserFilter())
async def user_state(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()

    try:
        target_id = int(message.text)
    except ValueError:
        DelayedMessage(await bot.send_message(user.id, get_section('warn/command/error/value')), 2).start()
        await state.clear()
        return

    target = session.scalar(select(User).where(User.fake_id == target_id))
    if not target:
        DelayedMessage(await bot.send_message(user.id, get_section('warn/command/error/user')), 2).start()
        await state.clear()
        return

    await handle_user_state(user=user, state=state, target_id=target_id)


async def handle_user_state(user: User, state: FSMContext, target_id: int):
    msg = await bot.send_message(user.id, get_section('warn/command/type'),
                                 reply_markup=ReplyKeyboardMarkup(
                                     keyboard=[[KeyboardButton(text=section['text'])]
                                               for section in get_section('rules/sections')]
                                              + [[KeyboardButton(text='Отмена')]]))
    await state.set_state(WarnStates.type)
    await state.set_data({'target_id': target_id, 'message': msg})


@router.message(WarnStates.type, UserFilter())
async def type_state(message: Message, user: User, state: FSMContext):
    sender = user
    await message.delete()
    await (await state.get_value('message')).delete()

    target = session.scalar(select(User).where(User.id == await state.get_value('target_id')))
    await state.clear()

    if message.text == 'Отмена':
        DelayedMessage(await bot.send_message(sender.id, 'Отменено',
                                              reply_markup=ReplyKeyboardRemove()), 2).start()
        return

    index = None
    for i, section in enumerate(get_section('rules/sections')):
        if section['text'] == message.text:
            index = i
            break

    if index is None:
        DelayedMessage(await bot.send_message(sender.id, get_section('warn/command/error/type'),
                                              reply_markup=ReplyKeyboardRemove()), 2).start()
        return

    warn = Warn(user=target, sender=sender, time=int(time.time()), section=index)
    session.add(warn)
    session.commit()
    register_warn(warn)

    warns = session.scalars(select(Warn).where(Warn.user == target, Warn.section == index)).all()
    count = len(warns)
    section = get_section('rules/sections')[index]
    after = section['penalty']['after'] + 1

    format_map = {'target': target,
                  'sender': sender,
                  'reason': section['text'],
                  'after': after,
                  'expire': time_to_str(section['penalty']['expire'] * 24 * 60 * 60),
                  'count': count}

    tasks = [bot.send_message(sender.id, get_section('warn/broadcast').format_map(format_map),
                              reply_markup=ReplyKeyboardRemove()),
             bot.send_message(target.id, get_section('warn/user').format_map(format_map))]

    for user in session.scalars(select(User).where(User.id != target.id, User.id != sender.id)).all():
        if user.ban:
            continue

        tasks += [bot.send_message(user.id, get_section('warn/broadcast').format_map(format_map))]

    await gather(*tasks)

    if after == count:
        types = {'mute': give_mute,
                 'ban': give_ban}

        await types[section['penalty']['type']](target, sender,
                                                section['penalty']['duration'] * 60 * 60,
                                                section['text'] + ' ({0}/{0})'.format(section['penalty']['after'] + 1))

        for warn in warns:
            session.delete(warn)
        session.commit()


def register_warn(warn: Warn):
    async def task(warn: Warn):
        section = get_section('rules/sections')[warn.section]
        remaining_time = max(warn.time + section['penalty']['expire'] * 60 * 60 * 24 - time.time(), 0)
        await sleep(remaining_time)
        if warn not in session:
            return
        logger.debug(f'Warn #{warn.id} is over')
        session.delete(warn)
        session.commit()

    create_task(task(warn))


def create_warn_tasks():
    for warn in session.scalars(select(Warn)).all():
        register_warn(warn)
