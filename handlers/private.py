from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from sqlalchemy import select

from database import User
from filters.command import UserCommand
from filters.user import UserFilter
from globals import bot, session
from states.private import PrivateStates
from utils import get_string, cancel_markup, hide_markup

router = Router()


@router.message(UserCommand('private', description=get_string('command_description/private')))
async def command(message: Message, user: User, state: FSMContext):
	await message.delete()
	msg = await bot.send_message(user.id, get_string('private/user'), reply_markup=cancel_markup)
	await state.set_state(PrivateStates.user)
	await state.set_data({'message': msg})


@router.message(UserFilter(), PrivateStates.user)
async def user(message: Message, user: User, state: FSMContext):
	await (await state.get_value('message')).delete()
	await message.delete()

	try:
		target_id = int(message.text)
	except ValueError:
		await bot.send_message(user.id, get_string('private/error/value'), reply_markup=hide_markup)
		return

	target = session.scalar(select(User).where(User.fake_id == target_id))
	if not target:
		await bot.send_message(user.id, get_string('private/error/user'), reply_markup=hide_markup)
		return

	await bot.send_message(user.id, get_string('private/joined').format(target),
						   reply_markup=ReplyKeyboardMarkup(
							   keyboard=[[KeyboardButton(text=get_string('private/exit'))]]))
	await state.set_state(PrivateStates.message)
	await state.set_data({'target': target})


@router.message(UserFilter(), F.text == get_string('private/exit'))
async def exit(message: Message, state: FSMContext, user: User):
	await state.clear()
	await message.delete()

	await bot.send_message(user.id, get_string('private/exited'), reply_markup=ReplyKeyboardRemove())
