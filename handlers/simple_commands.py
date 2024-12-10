import time

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from database import User
from filters.command import UserCommand
from filters.user import UserFilter
from globals import bot, session
from utils import hide_markup, get_string, get_unique_user_fake_id, time_to_str

router = Router()


@router.message(UserCommand('get_my_id', description=get_string('command_description/get_my_id')))
async def get_my_id(message: Message, user: User):
	await message.delete()
	await bot.send_message(user.id, f'Вы: {user.fake_id}', reply_markup=hide_markup)


@router.message(UserCommand('reset_my_id', description=get_string('command_description/reset_my_id')))
async def reset_my_id(message: Message, user: User):
	await message.delete()
	await bot.send_message(user.id, get_string('id/alert'), reply_markup=InlineKeyboardMarkup(
		inline_keyboard=[[InlineKeyboardButton(text='Сбросить', callback_data='reset_id')],
						 [InlineKeyboardButton(text='Отмена', callback_data='hide')]]))


@router.callback_query(F.data == 'reset_id', UserFilter())
async def reset_my_id_callback(callback: CallbackQuery, user: User):
	await callback.message.delete()

	current_time = int(time.time())
	remaining_time = user.last_id_reset_time + get_string('id/delay') - current_time
	if remaining_time > 0:
		await bot.send_message(user.id, get_string('id/debounce').format(time_to_str(remaining_time)),
							   reply_markup=hide_markup)
		return

	user.last_id_reset_time = current_time
	user.fake_id = get_unique_user_fake_id()
	await bot.send_message(user.id, get_string('id/reset').format(user.fake_id),
						   reply_markup=hide_markup)
