import html
import time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, KeyboardButton, Message, \
    ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from database import AdminPanelOpportunity, CommandOpportunity, Role, User
from filters.command import UserCommand
from filters.user import UserFilter
from globals import bot, session
from handlers.delayed import DelayedMessage
from states.user_profile import UserProfileStates
from utils import cancel_markup, get_section, hide_markup, time_to_str

router = Router()


@router.message(UserCommand('user_profile', description=get_section('command_description/user_profile'),
                            opportunity=CommandOpportunity.user_profile))
async def command(message: Message, user: User, state: FSMContext):
    await message.delete()
    msg = await bot.send_message(user.id, get_section('user_profile/user'), reply_markup=cancel_markup)
    await state.set_state(UserProfileStates.user)
    await state.set_data({'message': msg})


@router.message(UserProfileStates.user, UserFilter())
async def user(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()
    await state.clear()

    try:
        target_id = int(message.text)
    except ValueError:
        await bot.send_message(user.id, get_section('user_profile/error/value'), reply_markup=hide_markup)
        return

    target: User = session.scalar(select(User).where(User.fake_id == target_id))
    if not target:
        await bot.send_message(user.id, get_section('user_profile/error/user'), reply_markup=hide_markup)
        return

    chat = await bot.get_chat(target.id)
    text = html.escape(f'{get_section('id/display').format(target)} {chat.full_name}')
    if chat.username:
        text += f' (@{chat.username})'
    text += f'\n\nТГ ID: <a href="tg://user?id={target.id}">{target.id}</a>\n'
    text += f'С нами уже {time_to_str(int(time.time()) - target.joined_time)}\n'
    text += f'Написал {len(target.real_messages)} сообщений'
    if len(target.real_messages) > 0:
        text += f'\nПоследнее сообщение {time_to_str(int(time.time()) - target.real_messages[0].time)} назад'
    if chat.bio:
        text += f'\n\nОписание: {chat.bio}'

    keyboard = InlineKeyboardBuilder()
    if user.has_admin_panel_opportunity(AdminPanelOpportunity.CAN_SET_ROLES):
        keyboard.row(InlineKeyboardButton(text='Задать роль', callback_data=f'profile;{target.id};set_role'))
    keyboard.row(InlineKeyboardButton(text='Скрыть', callback_data='hide'))

    await bot.send_message(user.id, text, reply_markup=keyboard.as_markup())


@router.callback_query(F.data.split(';')[0] == 'profile', UserFilter())
async def callback(callback: CallbackQuery, user: User, state: FSMContext):
    args = callback.data.split(';')[1:]
    target_id = int(args[0])
    target = session.scalar(select(User).where(User.id == target_id))
    type = args[1]

    if type == 'set_role':
        msg = await bot.send_message(user.id, 'Выберите роль',
                                     reply_markup=ReplyKeyboardMarkup(keyboard=[[
                                         KeyboardButton(text=role.name)] for role in Role if role != target.role]
                                                                               + [[KeyboardButton(text='Отмена')]]))
        await state.set_state(UserProfileStates.set_role)
        await state.set_data({'message': msg, 'target_id': target_id})

    await callback.answer()


@router.message(UserProfileStates.set_role, UserFilter())
async def set_role_state(message: Message, user: User, state: FSMContext):
    await message.delete()
    await (await state.get_value('message')).delete()
    target_id = await state.get_value('target_id')
    await state.clear()

    if message.text == 'Отмена':
        DelayedMessage(await bot.send_message(user.id, 'Отменено', reply_markup=ReplyKeyboardRemove()), 2).start()
        return

    try:
        newrole = Role[message.text]
    except KeyError:
        DelayedMessage(await bot.send_message(user.id, 'Такой роли не существует',
                                              reply_markup=ReplyKeyboardRemove()), 2).start()
        return

    target = session.scalar(select(User).where(User.id == target_id))
    target.role = newrole

    DelayedMessage(await bot.send_message(user.id, 'Роль была изменена',
                                          reply_markup=ReplyKeyboardRemove()), 2).start()
    await bot.send_message(target.id, f'Ваша роль была изменена.\n'
                                      f'Теперь вы: {newrole}', reply_markup=hide_markup)
