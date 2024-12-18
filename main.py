import logging
from asyncio import run as run_async, gather, CancelledError

from aiogram import Dispatcher
from aiogram.loggers import event as event_logger
from sqlalchemy import select

from database import Base, User
from filters.log import InfoFilter
from globals import bot, engine, session, logger, IS_RELEASE, IS_DEBUG
from handlers import (start, rules, help, markup,
					  message, simple_commands, panel,
					  delete, private, warn, user_profile)
from handlers.log import LogHandler
from utils import update_user_commands, save_log


async def main():
	Base.metadata.create_all(engine)
	dispatcher = Dispatcher()

	event_logger.addFilter(InfoFilter())
	logging.basicConfig(level=logging.INFO if IS_RELEASE and not IS_DEBUG else logging.DEBUG, handlers=[LogHandler()])

	dispatcher.include_routers(start.router,
							   rules.router,
							   help.router,
							   markup.router,
							   simple_commands.router,
							   panel.router,
							   delete.router,
							   user_profile.router,
							   warn.router,
							   private.router,
							   message.router)

	tasks = []
	for user in session.scalars(select(User)).all():
		tasks += [update_user_commands(user)]
	await gather(*tasks)

	logger.info('Bot has started')

	try:
		await dispatcher.start_polling(bot, polling_timeout=30)
	except CancelledError:
		pass

	session.commit()
	engine.dispose()
	logger.info('Bot has stopped')
	await save_log()


if __name__ == '__main__':
	run_async(main())
