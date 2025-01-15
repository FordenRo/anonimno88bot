import sys
import time
from io import StringIO
from logging import getLogger

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import LinkPreviewOptions
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from yaml import safe_load as yaml_load

IS_RELEASE = 'release' in sys.argv
IS_DEBUG = 'debug' in sys.argv
START_TIME = int(time.time())
LOG_PATH = 'release.log' if IS_RELEASE else 'debug.log'
FILES_PATH = 'files' if IS_RELEASE else 'testfiles'
DATABASE_PATH = 'database.db' if IS_RELEASE else 'testdatabase.db'

TOKEN = '7968306540:AAFxs5V5AdedRzDiMqTpn9l1etMj-16wPBo' if IS_RELEASE \
        else '7754920336:AAGeVhk-VSkkmRP886RLEKNVWxASoU9coeA'
NOTIFICATION_TOKEN = '7818349534:AAFZoceGpZVyE0LO4mcAfUuRs6eikSQr_Gs' if IS_RELEASE \
        else '7571304760:AAF1kApcjfcbBgEUxkaROCwsOcMsI8ADHEQ'

BOT_NAME = 'anonimno88bot' if IS_RELEASE else 'jfeuUrJk23bot'
NOTIF_NAME = 'aj34FSjyrebot' if IS_RELEASE else 'gfUrGj43jcbot'

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode='HTML',
                                              protect_content=True,
                                              link_preview=LinkPreviewOptions(is_disabled=True)))
notif_bot = Bot(NOTIFICATION_TOKEN, default=DefaultBotProperties(parse_mode='HTML',
                                                                 link_preview=LinkPreviewOptions(is_disabled=True)))
notif_dispatcher = Dispatcher()

logger_stream = StringIO()
engine = create_engine(f'sqlite:///{DATABASE_PATH}')
session = Session(engine, expire_on_commit=False)
logger = getLogger()

with open('config.yaml', 'r', encoding='utf-8') as file:
    config = yaml_load(file)
