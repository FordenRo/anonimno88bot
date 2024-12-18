from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import User
from filters.command import UserCommand
from filters.user import UserFilter
from globals import bot
from utils import get_section, hide_markup

router = Router()


async def open_help(user: User):
    await bot.send_message(user.id, get_section('help/title'),
                           reply_markup=InlineKeyboardMarkup(
                               inline_keyboard=[[InlineKeyboardButton(text=data['title'],
                                                                      callback_data=f'help;{index}')]
                                                for index, data in enumerate(get_section('help/sections'))]
                                               + [[InlineKeyboardButton(text='Скрыть', callback_data='hide')]]))


@router.message(UserCommand('help', description=get_section('command_description/help')))
async def command(message: Message, user: User):
    await message.delete()
    await open_help(user)


@router.callback_query(F.data.split(';')[0] == 'help', UserFilter())
async def callback(callback: CallbackQuery, user: User):
    args = callback.data.split(';')
    if len(args) == 1:
        await open_help(user)
    else:
        section = int(args[1])

        await bot.send_message(callback.from_user.id,
                               '<b>{title}</b>\n\n{text}'.format(**get_section('help/sections')[section]),
                               reply_markup=hide_markup)
    await callback.answer()
