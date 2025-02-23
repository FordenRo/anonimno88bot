import logging
import time
from asyncio import CancelledError, create_task, gather, run as run_async, sleep

from aiogram import Dispatcher
from aiogram.enums import UpdateType
from aiogram.loggers import event as event_logger
from sqlalchemy import select
from sqlalchemy.exc import PendingRollbackError

from database import Base, RealMessage, User
from filters.log import InfoFilter
from globals import bot, engine, IS_DEBUG, IS_RELEASE, logger, notif_bot, session, notif_dispatcher
from handlers import (ban, delete, help, markup, message, mute, notification, panel, poll, private, rules,
                      simple_commands, start, user_profile, warn)
from handlers.log import LogHandler
from utils import save_log, time_to_str, update_user_commands


async def clean_messages():
    while True:
        curtime = time.time()
        for real_message in session.scalars(select(RealMessage)).all():
            await sleep(1)

            if curtime - real_message.time < 60 * 60 * 24:
                continue

            session.delete(real_message)
            logger.debug(f'deleted message of time {time_to_str(int(curtime) - real_message.time)}')

        session.commit()
        await sleep(5)


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
                               ban.router,
                               mute.router,
                               delete.router,
                               user_profile.router,
                               poll.router,
                               warn.router,
                               private.router,
                               message.router)

    notif_dispatcher.include_routers(notification.router)

    tasks = []
    for user in session.scalars(select(User)).all():
        tasks += [update_user_commands(user)]
    await gather(*tasks)
    cleaning_task = create_task(clean_messages())

    ban.create_ban_tasks()
    mute.create_mute_tasks()
    poll.create_poll_tasks()
    warn.create_warn_tasks()

    tasks = [dispatcher.start_polling(bot, polling_timeout=50,
                                      allowed_updates=[UpdateType.MESSAGE, UpdateType.CALLBACK_QUERY]),
             notif_dispatcher.start_polling(notif_bot, polling_timeout=50,
                                            allowed_updates=[UpdateType.MESSAGE, UpdateType.CALLBACK_QUERY])]
    try:
        await gather(*tasks)
    except CancelledError:
        pass

    try:
        session.commit()
    except PendingRollbackError as e:
        logger.error('Session has rolled back due to an error!', exc_info=e)
        session.rollback()

    engine.dispose()
    cleaning_task.cancel()

    await save_log()


if __name__ == '__main__':
    run_async(main())
