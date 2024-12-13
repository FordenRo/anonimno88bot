import time
from asyncio import gather

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import select

from database import User, CommandOpportunity, Warn
from filters.command import UserCommand
from filters.user import UserFilter
from globals import bot, session
from states.warn import WarnStates
from utils import get_section, hide_markup, time_to_str

router = Router()


@router.message(UserCommand('warn', description=get_section('command_description/warn'),
							opportunity=CommandOpportunity.warn))
async def command(message: Message, user: User, state: FSMContext):
	await message.delete()
	msg = await bot.send_message(user.id, get_section('warn/command/user'))
	await state.set_state(WarnStates.user)
	await state.set_data({'message': msg})


@router.message(WarnStates.user, UserFilter())
async def user_state(message: Message, user: User, state: FSMContext):
	await message.delete()
	await (await state.get_value('message')).delete()

	try:
		target_id = int(message.text)
	except ValueError:
		await bot.send_message(user.id, get_section('warn/command/error/value'))
		return

	target = session.scalar(select(User).where(User.fake_id == target_id))
	if not target:
		await bot.send_message(user.id, get_section('warn/command/error/user'))
		return

	msg = await bot.send_message(user.id, get_section('warn/command/type'),
								 reply_markup=ReplyKeyboardMarkup(
									 keyboard=[[KeyboardButton(text=section['text'])]
											   for section in get_section('rules/sections')]))
	await state.set_state(WarnStates.type)
	await state.set_data({'target_id': target.id, 'message': msg})


@router.message(WarnStates.type, UserFilter())
async def type_state(message: Message, user: User, state: FSMContext):
	sender = user
	await message.delete()
	await (await state.get_value('message')).delete()

	target = session.scalar(select(User).where(User.id == await state.get_value('target_id')))
	await state.clear()

	index = None
	for i, section in enumerate(get_section('rules/sections')):
		if section['text'] == message.text:
			index = i
			break

	if not index:
		await bot.send_message(sender.id, get_section('warn/command/error/type'), reply_markup=hide_markup)
		return

	warn = Warn(user=target, sender=sender, time=int(time.time()), section=index)
	session.add(warn)
	session.commit()

	count = len(session.scalars(select(Warn).where(Warn.user == target, Warn.section == index)).all())
	section = get_section('rules/sections')[index]
	after = section['penalty']['after'] + 1

	format_map = {'target': target,
				  'sender': sender,
				  'reason': section['text'],
				  'after': after,
				  'expire': time_to_str(section['penalty']['expire'] * 24 * 60 * 60),
				  'count': count}

	tasks = []
	for user in session.scalars(select(User).where(User.id != target.id)).all():
		tasks += [bot.send_message(user.id, get_section('warn/broadcast').format_map(format_map))]
	tasks += [bot.send_message(target.id, get_section('warn/user').format_map(format_map))]

	await gather(*tasks)
