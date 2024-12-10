from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from filters.command import UserCommand
from globals import bot
from utils import get_string, hide_markup

router = Router()


@router.message(UserCommand('rules', description=get_string('command_description/rules')))
async def command(message: Message):
	await message.delete()
	await bot.send_message(message.from_user.id, get_string('rules'), reply_markup=hide_markup)


@router.callback_query(F.data == 'rules')
async def callback(callback: CallbackQuery):
	await bot.send_message(callback.from_user.id, get_string('rules'), reply_markup=hide_markup)
	await callback.answer()
