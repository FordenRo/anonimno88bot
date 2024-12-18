import sys
import time
from logging import Handler
from types import TracebackType

from globals import logger_stream


class LogHandler(Handler):
    def handle(self, record):
        if record.exc_info:
            type = record.exc_info[0].__name__
            exception: BaseException = record.exc_info[1]
            traceback: TracebackType = record.exc_info[2]
            formatted_message = f'[{time.strftime('%H:%M:%S')} {record.name}/{record.levelname}] {type} at line {traceback.tb_lineno} in {traceback.tb_frame.f_code.co_name}: {' '.join(exception.args)} ({record.getMessage()})'
        else:
            formatted_message = f'[{time.strftime('%H:%M:%S')} {record.name}/{record.levelname}] {record.getMessage()}'

        logger_stream.write(formatted_message + '\n')
        if record.levelname == "ERROR":
            sys.stderr.write(formatted_message + '\n')
        else:
            sys.stdout.write(formatted_message + '\n')

        return True
