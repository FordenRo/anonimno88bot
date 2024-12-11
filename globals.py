import sys
import time
from io import StringIO
from logging import getLogger

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.types import LinkPreviewOptions
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from yaml import safe_load as yaml_load

IS_RELEASE = 'release' in sys.argv
START_TIME = int(time.time())
LOG_PATH = 'release.log' if IS_RELEASE else 'debug.log'

bot = Bot('7430750632:AAGhNMrwZwTxJTiriFvOD02hxGhcMXdVLBQ',
		  default=DefaultBotProperties(parse_mode='HTML',
									   protect_content=True,
									   link_preview=LinkPreviewOptions(is_disabled=True)))
logger_stream = StringIO()
engine = create_engine('sqlite:///testdatabase.db')
session = Session(engine)
logger = getLogger()

with open('strings.yaml', 'r', encoding='utf-8') as file:
	messages = yaml_load(file)
