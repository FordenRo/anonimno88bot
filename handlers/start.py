import os.path
import time
from asyncio import create_task

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from sqlalchemy import exists, select

from database import User, Opportunity, Role
from globals import session, bot
from utils import get_string, text_inline_markup, update_user_commands, get_unique_user_fake_id, hide_markup

router = Router()


@router.message(CommandStart())
async def start(message: Message):
	await message.delete()

	if session.query(exists(User).where(User.id == message.from_user.id)).scalar():
		user = session.scalar(select(User).where(User.id == message.from_user.id))
	else:
		user = User(id=message.from_user.id, fake_id=get_unique_user_fake_id(), joined_time=int(time.time()))
		session.add(user)
		session.commit()

		if user.id == 7625373673:
			user.role = Role.OWNER

		create_task(new_user_notification(user))

		await bot.send_animation(user.id,
								 FSInputFile(get_string('welcome/animation'),
											 os.path.basename(get_string('welcome/animation'))),
								 caption=get_string('welcome/message'),
								 reply_markup=text_inline_markup(get_string('welcome/buttons')))

	await update_user_commands(user)


async def new_user_notification(user: User):
	for target in session.scalars(select(User).where(User.id != user.id)):
		if target.has_opportunity(Opportunity.CAN_RECEIVE_USER_JOINED_BANNED_MESSAGE):
			chat = await bot.get_chat(user.id)
			await bot.send_message(target.id,
								   f'Новый {user.role!s} №{user.fake_id} {chat.full_name} '
								   f'({f'@{chat.username}' if chat.username else f'id_{user.id}'})',
								   reply_markup=hide_markup)
