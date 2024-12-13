from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from database import User, CommandOpportunity
from filters.command import UserCommand
from filters.user import UserFilter
from states.user_profile import UserProfileStates
from globals import bot, session
from utils import hide_markup, cancel_markup, get_string

router = Router()


@router.message(UserCommand('user_profile', description=get_string('command_description/user_profile'), opportunity=CommandOpportunity.user_profile))
async def command(message: Message, user: User, state: FSMContext):
	await message.delete()
	msg = await bot.send_message(user.id, get_string('user_profile/user'), reply_markup=cancel_markup)
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
		await bot.send_message(user.id, get_string('user_profile/error/value'), reply_markup=hide_markup)
		return

	target = session.scalar(select(User).where(User.fake_id == target_id))
	if not target:
		await bot.send_message(user.id, get_string('user_profile/error/user'), reply_markup=hide_markup)
		return

	chat = await bot.get_chat(target.id)
	text = f"{get_string('id/display').format(target)} {chat.full_name}"
	if chat.username:
		text += f' (@{chat.username})'
	text += f'ID: {target.id}'
	if chat.bio:
		text += f'\nBIO: {chat.bio}'

	await bot.send_message(user.id, text, reply_markup=hide_markup)

