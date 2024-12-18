import logging
import time
from asyncio import CancelledError, create_task, gather, run as run_async, sleep

from aiogram import Dispatcher
from aiogram.enums import UpdateType
from aiogram.loggers import event as event_logger
from sqlalchemy import select

from database import Base, RealMessage, User
from filters.log import InfoFilter
from globals import bot, engine, IS_DEBUG, IS_RELEASE, logger, session
from handlers import (delete, help, markup, message, panel, private, rules, simple_commands, start, user_profile, warn)
from handlers.log import LogHandler
from utils import save_log, time_to_str, update_user_commands


async def clean_messages():
    while True:
        curtime = time.time()
        for real_message in session.scalars(select(RealMessage)).all():
            await sleep(0.01)

            if curtime - real_message.time < 60 * 60 * 24:
                continue

            for fake_message in real_message.fake_messages:
                session.delete(fake_message)

            session.delete(real_message)
            logger.debug(f'deleted message of time {time_to_str(int(curtime) - real_message.time)}')

        session.commit()
        await sleep(1)


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
    cleaning_task = create_task(clean_messages())

    logger.info('Bot has started')

    try:
        await dispatcher.start_polling(bot, polling_timeout=50,
                                       allowed_updates=[UpdateType.MESSAGE, UpdateType.CALLBACK_QUERY])
    except CancelledError:
        pass

    session.commit()
    engine.dispose()
    cleaning_task.cancel()
    logger.info('Bot has stopped')
    await save_log()


if __name__ == '__main__':
    run_async(main())
