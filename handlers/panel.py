import time

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, CallbackQuery
from sqlalchemy import select
from sqlalchemy.sql.functions import count

from database import User, AdminPanelOpportunity, CommandOpportunity
from filters.command import UserCommand
from filters.user import UserFilter
from globals import bot, session, start_time
from utils import get_string, time_to_str, hide_markup

router = Router()


@router.message(UserCommand('panel', description=get_string('command_description/panel'), opportunity=CommandOpportunity.panel))
async def command(message: Message, user: User):
	await message.delete()

	reply_markup = InlineKeyboardMarkup(
		inline_keyboard=[[InlineKeyboardButton(text=button[0], callback_data=button[1]) for button in row
						  if len(button) < 3 or user.has_admin_panel_opportunity(AdminPanelOpportunity[button[2]])]
						 for row in get_string('panel/buttons')])

	await bot.send_photo(user.id,
						 FSInputFile(get_string('panel/image'), get_string('panel/image')),
						 reply_markup=reply_markup)


@router.callback_query(F.data == 'panel;stats', UserFilter())
async def callback(callback: CallbackQuery, user: User):
	await bot.send_message(user.id, f'Статистика:\n\n'
									f'Кол-во пользователей: {session.scalar(select(count()).select_from(User))}\n'
									f'Время работы: {time_to_str(int(time.time() - start_time))}',
						   reply_markup=hide_markup)
	await callback.answer()


@router.callback_query(F.data == 'panel;user_list', UserFilter())
async def user_list(callback: CallbackQuery, user: User, state: FSMContext):
	index = int(callback.data.split(';')[2:] or -1)
	await callback.answer()
