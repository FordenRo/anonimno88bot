import time

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile
from sqlalchemy import exists, select

from database import User
from globals import session, bot
from utils import get_string, text_inline_markup, update_user_commands, get_unique_user_fake_id

router = Router()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
	await message.delete()

	if session.query(exists(User).where(User.id == message.from_user.id)).scalar():
		user = session.scalar(select(User).where(User.id == message.from_user.id))
	else:
		user = User(id=message.from_user.id, fake_id=get_unique_user_fake_id(), joined_time=int(time.time()))
		session.add(user)
		session.commit()

		await bot.send_animation(user.id, FSInputFile(get_string('welcome/animation'), 'welcome.gif'),
								 caption=get_string('welcome/message'),
								 reply_markup=text_inline_markup(get_string('welcome/buttons')))

	await update_user_commands(user)
