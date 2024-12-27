import time
from asyncio import create_task, sleep

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, \
    ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy import select

from database import CommandOpportunity, Opportunity, Poll, PollAnswer, PollVariant, User
from filters.command import UserCommand
from filters.user import UserFilter
from globals import bot, logger, session
from handlers.delayed import DelayedMessage
from states.poll import PollStates
from utils import cancel_markup, get_section, hide_markup, time_to_str

router = Router()


@router.message(UserCommand('poll', description=get_section('command_description/poll'),
                            opportunity=CommandOpportunity.poll))
async def command(message: Message, user: User, state: FSMContext):
    await message.delete()
    msg = await bot.send_message(user.id, get_section('poll/command/description'), reply_markup=cancel_markup)
    await state.set_state(PollStates.description)
    await state.set_data({'message': msg})


@router.message(PollStates.description, UserFilter())
async def description(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()

    msg = await bot.send_message(user.id, get_section('poll/command/duration'), reply_markup=cancel_markup)
    await state.set_state(PollStates.duration)
    await state.set_data({'message': msg, 'description': message.text})


@router.message(PollStates.duration, UserFilter())
async def duration(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()
    description = await state.get_value('description')

    try:
        duration = int(float(message.text) * 60 * 60)
    except ValueError:
        DelayedMessage(await bot.send_message(user.id, get_section('poll/error/duration')), 2).start()
        await state.clear()
        return

    poll = Poll(time=int(time.time()), sender=user, description=description, duration=duration)
    session.add(poll)
    session.commit()

    register_poll(poll)

    await state.set_data({'poll_id': poll.id})
    await request_variant(user, state)


async def request_variant(user: User, state: FSMContext):
    msg = await bot.send_message(user.id, get_section('poll/command/variant'), reply_markup=cancel_markup)
    poll_id = await state.get_value('poll_id')
    await state.set_state(PollStates.variant)
    await state.set_data({'message': msg, 'poll_id': poll_id})


@router.message(PollStates.variant, UserFilter())
async def variant_state(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()
    poll_id = await state.get_value('poll_id')

    variant = PollVariant(text=message.text, poll_id=poll_id)
    session.add(variant)
    session.commit()

    msg = await bot.send_message(user.id, get_section('poll/command/more'),
                                 reply_markup=ReplyKeyboardMarkup(
                                     keyboard=[[KeyboardButton(text='Добавить')],
                                               [KeyboardButton(text='Создать опрос')]]))
    await state.set_state(PollStates.more)
    await state.set_data({'message': msg, 'poll_id': poll_id})


@router.message(PollStates.more, UserFilter())
async def more_state(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()

    if message.text == 'Добавить':
        await request_variant(user, state)
    elif message.text == 'Создать опрос':
        poll_id = await state.get_value('poll_id')
        poll = session.scalar(select(Poll).where(Poll.id == poll_id))
        await state.clear()
        session.commit()

        DelayedMessage(await bot.send_message(user.id, get_section('poll/command/created'),
                                              reply_markup=ReplyKeyboardRemove()), 2).start()
        await send_poll(poll)


@router.callback_query(F.data.split()[0] == 'poll', UserFilter())
async def callback(callback: CallbackQuery, user: User):
    args = callback.data.split()[2:]
    type = callback.data.split()[1]

    async def answer():
        id, = args
        variant = session.scalar(select(PollVariant).where(PollVariant.id == id))
        if not variant:
            await callback.answer(get_section('poll/error/expired'), True)
            await callback.message.delete()
            return

        answer = session.scalar(select(PollAnswer).where(PollAnswer.user == user,
                                                         PollAnswer.poll == variant.poll))
        if answer:
            await callback.answer(get_section('poll/error/chosen'), True)
            return

        answer = PollAnswer(variant=variant, user=user, time=int(time.time()), poll=variant.poll)
        session.add(answer)
        session.commit()

        keyboard = None
        if user.has_opportunity(Opportunity.CAN_SEE_POLL_INFO):
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text='Информация',
                                                       callback_data=f'poll info {variant.poll_id}')]])

        await callback.message.edit_text(f'<b>{variant.poll.description}</b>\n\nВаш выбор: <i>{variant.text}</i>',
                                         reply_markup=keyboard)
        await callback.answer(get_section('poll/answered'))

    async def info():
        id, = args
        poll = session.scalar(select(Poll).where(Poll.id == id))
        if not poll:
            await callback.answer(get_section('poll/error/expired'), True)
            await callback.message.delete()
            return

        curtime = time.time()
        await bot.send_message(user.id, '\n\n'.join(
            [f'{variant.text} ({len(variant.answers)} - {len(variant.answers) / len(poll.answers):.0%}):\n'
             f'{'\n'.join([f'{answer.user.role} №{answer.user.fake_id} '
                           f'{time_to_str(curtime - answer.time)} назад'
                           for answer in variant.answers])}'
             for variant in poll.variants]), reply_markup=hide_markup)
        await callback.answer()

    types = {'answer': lambda: answer(),
             'info': lambda: info()}
    await types[type]()


async def send_poll(poll: Poll):
    for user in session.scalars(select(User)).all():
        keyboard = [[InlineKeyboardButton(text=variant.text, callback_data=f'poll answer {variant.id}')]
                    for variant in poll.variants]

        if user.has_opportunity(Opportunity.CAN_SEE_POLL_INFO):
            keyboard += [[InlineKeyboardButton(text='Информация', callback_data=f'poll info {poll.id}')]]

        await bot.send_message(user.id, f'<b>{poll.description}</b>',
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

    session.commit()


def register_poll(poll: Poll):
    async def task(poll: Poll):
        remaining_time = max(poll.time + poll.duration - time.time(), 0)
        await sleep(remaining_time)
        if poll not in session:
            return
        logger.debug(f'Poll #{poll.id} is over')
        session.delete(poll)
        session.commit()

    create_task(task(poll))


def create_poll_tasks():
    for poll in session.scalars(select(Poll)).all():
        register_poll(poll)
