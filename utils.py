from random import randint

from aiofiles import open
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, BotCommandScopeChat
from sqlalchemy import select

from database import User, FakeMessage, RealMessage
from filters.command import UserCommand
from globals import config, bot, session, LOG_PATH, logger_stream

hide_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Скрыть', callback_data='hide')]])
cancel_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data='cancel')]])


def get_section(path: str) -> any:
	def parse(text: str):
		start = text.find('$') + 1
		if start == 0:
			return text
		end = text.find('$', start)
		replace = get_section(text[start:end])
		text = text[:start - 1] + replace + text[end + 1:]
		return parse(text)

	path = path.split('/')
	obj = config
	for section in path:
		obj = obj[section]
	if isinstance(obj, str):
		return parse(obj)
	return obj


def text_inline_markup(markup: list[tuple[str, str]]) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[[InlineKeyboardButton(text=button[0], callback_data=button[1]) for button in row] for row in
						 markup])


async def update_user_commands(user: User):
	await bot.set_my_commands([BotCommand(command=command.commands[0], description=command.description)
							   for command in UserCommand.command_list
							   if user.has_command_opportunity(command.opportunity)],
							  scope=BotCommandScopeChat(chat_id=user.id))


# TODO
def get_user_fake_message_from_real(real_message: RealMessage, user: User):
	return select(FakeMessage).select_from(RealMessage.fake_messages)


def get_unique_user_fake_id():
	users = session.scalars(select(User)).all()
	reserved_ids = [user.fake_id for user in users]
	ids = list(filter(lambda id: id not in reserved_ids, range(10, int(len(users) * 1.2) + 30)))
	if len(ids) == 0:
		return 10
	return ids[randint(0, len(ids) - 1)]


def time_to_str(time: int):
	second = int(time) % 60
	minute = int(time / 60) % 60
	hour = int(time / 60 / 60) % 24
	day = int(time / 60 / 60 / 24) % 30
	month = int(time / 60 / 60 / 24 / 30)

	array = []
	if month:
		array += [f'{month} мес']
	if day:
		array += [f'{day} д']
	if not month and hour:
		array += [f'{hour} ч']
	if not month and not day and minute:
		array += [f'{minute} м']
	if not month and not day and not hour and second:
		array += [f'{second} с']

	return ' '.join(array)


async def save_log():
	async with open(LOG_PATH, 'w') as file:
		await file.write(logger_stream.getvalue())
