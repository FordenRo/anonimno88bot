import time

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import User
from filters.command import UserCommand
from filters.user import UserFilter
from globals import bot
from utils import get_section, get_unique_user_fake_id, hide_markup, time_to_str

router = Router()


@router.message(UserCommand('get_my_id', description=get_section('command_description/get_my_id')))
async def get_my_id(message: Message, user: User):
    await message.delete()
    await bot.send_message(user.id, get_section('id/message').format(user), reply_markup=hide_markup)


@router.message(UserCommand('reset_my_id', description=get_section('command_description/reset_my_id')))
async def reset_my_id(message: Message, user: User):
    await message.delete()
    await bot.send_message(user.id, get_section('id/alert'), reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text='Сбросить', callback_data='reset_id')],
                         [InlineKeyboardButton(text='Отмена', callback_data='hide')]]))


@router.callback_query(F.data == 'reset_id', UserFilter())
async def reset_my_id_callback(callback: CallbackQuery, user: User):
    await callback.message.delete()

    current_time = int(time.time())
    remaining_time = user.last_id_reset_time + get_section('id/delay') - current_time
    if remaining_time > 0:
        await bot.send_message(user.id, get_section('id/debounce').format(time_to_str(remaining_time)),
                               reply_markup=hide_markup)
        return

    user.last_id_reset_time = current_time
    user.fake_id = get_unique_user_fake_id()
    await bot.send_message(user.id, get_section('id/reset').format(user.fake_id),
                           reply_markup=hide_markup)
