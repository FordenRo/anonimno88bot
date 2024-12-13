from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from database import User
from filters.command import UserCommand
from filters.user import UserFilter
from globals import bot
from utils import get_section, hide_markup, time_to_str

router = Router()


async def open(user: User):
	penalty_types = {'mute': 'мут',
					 'ban': 'бан'}

	sections = '\n\n'.join([get_section('rules/section').format(index=i + 1,
																after=section['penalty']['after'],
																text=section['text'],
																type=penalty_types[section['penalty']['type']],
																time=time_to_str(
																   section['penalty']['duration'] * 60 * 60))
							for i, section in enumerate(get_section('rules/sections'))])

	await bot.send_message(user.id,
						   '\n\n'.join([get_section('rules/title'), sections]),
						   reply_markup=hide_markup)


@router.message(UserCommand('rules', description=get_section('command_description/rules')))
async def command(message: Message, user: User):
	await message.delete()
	await open(user)


@router.callback_query(F.data == 'rules', UserFilter())
async def callback(callback: CallbackQuery, user: User):
	await open(user)
	await callback.answer()
