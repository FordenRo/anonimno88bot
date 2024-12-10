import time
from logging import getLogger
import yaml
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.types import LinkPreviewOptions
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

bot = Bot('7430750632:AAGhNMrwZwTxJTiriFvOD02hxGhcMXdVLBQ',
		  default=DefaultBotProperties(parse_mode='HTML',
									   protect_content=True,
									   link_preview=LinkPreviewOptions(is_disabled=True)))
start_time = int(time.time())
engine = create_engine('sqlite:///testdatabase.db', echo=True)
session = Session(engine)
logger = getLogger()

with open('strings.yaml', 'r', encoding='utf-8') as file:
	messages = yaml.safe_load(file)
