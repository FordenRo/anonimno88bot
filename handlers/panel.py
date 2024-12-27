import html
import os.path
import time
from asyncio import create_task, gather
from itertools import batched

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select, text as sql_text
from sqlalchemy.sql.functions import count

from database import AdminPanelOpportunity, Ban, CommandOpportunity, Mute, Poll, User
from filters.command import UserCommand
from filters.user import UserFilter
from globals import bot, DATABASE_PATH, LOG_PATH, logger_stream, session, START_TIME
from states.panel import PanelStates
from utils import cancel_markup, get_section, hide_markup, save_log, time_to_str

router = Router()


@router.message(UserCommand('panel',
                            description=get_section('command_description/panel'),
                            opportunity=CommandOpportunity.panel))
async def command(message: Message, user: User):
    await message.delete()

    reply_markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=button[0], callback_data=button[1]) for button in row
                          if len(button) < 3 or user.has_admin_panel_opportunity(AdminPanelOpportunity[button[2]])]
                         for row in get_section('panel/buttons')])

    await bot.send_photo(user.id,
                         FSInputFile(get_section('panel/image'), os.path.basename(get_section('panel/image'))),
                         reply_markup=reply_markup)


@router.callback_query(F.data == 'panel;stats', UserFilter())
async def stats(callback: CallbackQuery, user: User):
    await bot.send_message(user.id, f'Статистика:\n\n'
                                    f'Кол-во пользователей: {session.scalar(select(count()).select_from(User))}\n'
                                    f'Кол-во банов: {session.scalar(select(count()).select_from(Ban))}\n'
                                    f'Кол-во мутов: {session.scalar(select(count()).select_from(Mute))}\n'
                                    f'Кол-во опросов: {session.scalar(select(count()).select_from(Poll))}'
                                    f'Время работы: {time_to_str(int(time.time() - START_TIME))}\n'
                                    f'Вес БД: {os.path.getsize(DATABASE_PATH)}',
                           reply_markup=hide_markup)
    await callback.answer()


@router.callback_query(F.data.split(';')[:2] == ['panel', 'user_list'], UserFilter())
async def user_list(callback: CallbackQuery, user: User):
    index = callback.data.split(';')[2:]
    edit = index
    index = int(index[0]) if index else 0
    pages = list(batched(session.scalars(select(User)).all(), 15))

    async def get_user_info(user: User):
        chat = await bot.get_chat(user.id)
        return html.escape(f'{str(user.role)} №{user.fake_id} {chat.full_name}'
                           f' ({f'@{chat.username}' if chat.username else f'id_{user.id}'})')

    tasks = [create_task(get_user_info(user)) for user in pages[index]]
    infos = await gather(*tasks)

    btns = []
    if index > 0:
        btns += [InlineKeyboardButton(text='Назад', callback_data=f'panel;user_list;{index - 1}')]
    if index + 1 != len(pages):
        btns += [InlineKeyboardButton(text='Вперед', callback_data=f'panel;user_list;{index + 1}')]

    kb = InlineKeyboardMarkup(inline_keyboard=[btns] + [[InlineKeyboardButton(text='Закрыть', callback_data='hide')]])
    page_string = f'Список пользователей ({index + 1}/{len(pages)})\n'
    text = '\n'.join([page_string] + infos)
    if edit:
        await callback.message.edit_text(text, reply_markup=kb)
    else:
        await bot.send_message(user.id, text, reply_markup=kb)

    await callback.answer()


@router.callback_query(F.data.split(';')[:2] == ['panel', 'log'], UserFilter())
async def log(callback: CallbackQuery, user: User):
    index = callback.data.split(';')[2:]
    edit = index
    index = int(index[0]) if index else 0
    pages = list(batched(str(logger_stream.getvalue()).splitlines()[::-1], 12))

    btns = []
    if index > 0:
        btns += [InlineKeyboardButton(text='Назад', callback_data=f'panel;log;{index - 1}')]
    if index + 1 != len(pages):
        btns += [InlineKeyboardButton(text='Вперед', callback_data=f'panel;log;{index + 1}')]

    control_buttons = [InlineKeyboardButton(text='Файл', callback_data='panel;log_file'),
                       InlineKeyboardButton(text='Закрыть', callback_data='hide')]

    kb = InlineKeyboardMarkup(inline_keyboard=[btns] + [control_buttons])
    page_string = f'Лог ({index + 1}/{len(pages)})\n'
    text = '\n'.join([page_string] + list(pages[index]))
    if edit:
        await callback.message.edit_text(text, reply_markup=kb)
    else:
        await bot.send_message(user.id, text, reply_markup=kb)

    await callback.answer()


@router.callback_query(F.data == 'panel;execute', UserFilter())
async def db_execute(callback: CallbackQuery, user: User, state: FSMContext):
    msg = await bot.send_message(user.id, 'Введите команду', reply_markup=cancel_markup)
    await callback.answer()
    await state.set_state(PanelStates.execute)
    await state.set_data({'message': msg})


@router.message(PanelStates.execute, UserFilter())
async def execute_state(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()
    await state.clear()

    try:
        text = '\n'.join([str(i) for i in session.execute(sql_text(message.text)).scalars()])

        if not text:
            await bot.send_message(user.id, 'No output', reply_markup=hide_markup)
            return

        await bot.send_message(user.id, text, reply_markup=hide_markup)
    except Exception as e:
        await bot.send_message(user.id, f'Error: {e!s}', reply_markup=hide_markup)


@router.callback_query(F.data == 'panel;log_file', UserFilter())
async def send_log_file(callback: CallbackQuery, user: User):
    await callback.answer('Отправление...')
    await save_log()
    await bot.send_document(user.id, FSInputFile(LOG_PATH, os.path.basename(LOG_PATH)),
                            reply_markup=hide_markup, protect_content=False)
