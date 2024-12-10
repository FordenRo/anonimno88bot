from asyncio import run as run_async, sleep as sleep_async, create_task, gather

from aiogram import Dispatcher
from sqlalchemy import select

from handlers import start, rules, help, markup, message, simple_commands, panel
from database import Base, User, DelayedMessage, Role
from globals import bot, engine, session
from utils import update_user_commands


async def delayed_messages_task():
	while True:
		await sleep_async(1)

		async def task(message: DelayedMessage):
			await sleep_async(message.delay)

			try:
				await bot.delete_message(message.chat_id, message.message_id)
			except:
				pass

		for message in session.scalars(select(DelayedMessage)).all():
			create_task(task(message))
			session.delete(message)


async def main():
	Base.metadata.create_all(engine)
	dispatcher = Dispatcher()

	dispatcher.include_routers(start.router,
							   rules.router,
							   help.router,
							   markup.router,
							   simple_commands.router,
							   panel.router,
							   message.router)

	for user in session.scalars(select(User)).all():
		await update_user_commands(user)

	tasks = gather(delayed_messages_task())

	await dispatcher.start_polling(bot)

	tasks.cancel()
	await session.commit()
	await engine.dispose()


if __name__ == '__main__':
	run_async(main())
