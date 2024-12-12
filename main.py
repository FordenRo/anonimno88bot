import logging
from asyncio import run as run_async

from aiogram import Dispatcher
from sqlalchemy import select

from database import Base, User
from globals import bot, engine, session, logger, IS_RELEASE
from handlers import start, rules, help, markup, message, simple_commands, panel, delete, private
from handlers.log import LogHandler
from utils import update_user_commands, save_log


async def main():
	Base.metadata.create_all(engine)
	dispatcher = Dispatcher()

	logging.basicConfig(level=logging.INFO if IS_RELEASE else logging.DEBUG, handlers=[LogHandler()])

	dispatcher.include_routers(start.router,
							   rules.router,
							   help.router,
							   markup.router,
							   simple_commands.router,
							   panel.router,
							   delete.router,
							   private.router,
							   message.router)

	for user in session.scalars(select(User)).all():
		await update_user_commands(user)

	logger.info('Bot has started')
	await dispatcher.start_polling(bot)

	session.commit()
	engine.dispose()
	logger.info('Bot has stopped')
	save_log()


if __name__ == '__main__':
	run_async(main())
