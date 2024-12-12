from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from filters.command import UserCommand
from globals import bot
from utils import get_string, hide_markup

router = Router()


@router.message(UserCommand('help', description=get_string('command_description/help')))
async def command(message: Message):
	await message.delete()
	await bot.send_message(message.from_user.id, get_string('help/message'),
						   reply_markup=InlineKeyboardMarkup(
							   inline_keyboard=[[InlineKeyboardButton(text=data[0], callback_data=f'help;{i}')] for
												i, data in enumerate(get_string('help/buttons'))]
											   + [[InlineKeyboardButton(text='Скрыть', callback_data='hide')]]))


@router.callback_query(F.data.split(';')[0] == 'help')
async def callback(callback: CallbackQuery):
	args = callback.data.split(';')
	if len(args) == 1:
		await bot.send_message(callback.from_user.id, get_string('help/message'),
							   reply_markup=InlineKeyboardMarkup(
								   inline_keyboard=[[InlineKeyboardButton(text=data[0], callback_data=f'help;{i}')]
													for i, data in enumerate(get_string('help/buttons'))]
												   + [[InlineKeyboardButton(text='Скрыть', callback_data='hide')]]))
	else:
		section = int(args[1])

		await bot.send_message(callback.from_user.id,
							   '<b>{0}</b>\n\n{1}'.format(*get_string('help/buttons')[section]),
							   reply_markup=hide_markup)
	await callback.answer()
