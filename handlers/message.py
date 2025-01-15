import html
import os.path
import re
import time
from asyncio import create_task, gather

from aiofiles.os import makedirs
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyParameters
from sqlalchemy import select

from database import FakeMessage, Opportunity, RealMessage, User
from filters.user import UserFilter
from globals import bot, FILES_PATH, logger, notif_bot, session, START_TIME, BOT_NAME
from handlers.delayed import DelayedMessage
from utils import get_section, join_strings_at_index, time_to_str

router = Router()


@router.message(UserFilter())
async def message(message: Message, user: User, state: FSMContext):
    sender = user
    target = await state.get_value('target')
    text = message.text or message.caption
    content_type = message.content_type.name.lower()
    file_id = getattr(getattr(message, content_type), 'file_id', None)
    reply_to = None
    current_time = int(time.time())
    debug_time = time.time()

    if content_type == 'photo':
        file_id = message.photo[-1].file_id

    debounce = get_section(f'debounce/{content_type}/delay')
    remaining_time = int(sender.get_last_message_time(content_type) + debounce - current_time)
    if (current_time > START_TIME + 5
            and remaining_time > 0
            and not sender.has_opportunity(Opportunity.NO_MESSAGE_DELAY)):
        await message.delete()

        DelayedMessage(await bot.send_message(sender.id, get_section(f'debounce/{content_type}/message')
                                              .format(time_to_str(remaining_time))), 2).start()
        return

    if message.reply_to_message:
        reply_to = getattr(
            session.scalar(select(FakeMessage).where(FakeMessage.id == message.reply_to_message.message_id)),
            'real_message',
            session.scalar(select(RealMessage).where(RealMessage.id == message.reply_to_message.message_id)))

    sender.set_last_message_time(content_type, current_time)
    real_message = RealMessage(id=message.message_id, sender=sender, target=target, type=content_type, text=text,
                               file_id=file_id, reply_to=reply_to, time=current_time)
    session.add(real_message)
    session.commit()

    async def send(real_message: RealMessage, user: User):
        if user.ban:
            return

        text = '\n\n'.join(([real_message.text] if real_message.text else [])
                           + [get_section('id/display').format(real_message.sender)])
        kbtext = f'№{real_message.sender.fake_id}'
        if real_message.target:
            text += ' -> ' + ('<b>Вам</b>' if real_message.target == user
                              else get_section('id/display').format(real_message.target))
            kbtext += ' -> ' + ('Вам' if real_message.target == user
                                else f'№{real_message.target.fake_id}')

        if user.has_opportunity(Opportunity.CAN_SEE_USERNAMES):
            chat = await bot.get_chat(real_message.sender.id)
            text += html.escape(f'\n{chat.full_name}')
            if chat.username:
                text += f' (@{chat.username})'

            if real_message.target:
                chat = await bot.get_chat(real_message.target.id)
                text += html.escape(f'\n{chat.full_name}')
                if chat.username:
                    text += f' (@{chat.username})'

        reply_parameters = None
        if real_message.reply_to:
            if real_message.reply_to.sender == user:
                reply_parameters = ReplyParameters(message_id=real_message.reply_to.id)
            else:
                reply_message = session.scalar(
                    select(FakeMessage).where(FakeMessage.real_message == real_message.reply_to,
                                              FakeMessage.user == user))
                if reply_message:
                    reply_parameters = ReplyParameters(message_id=reply_message.id)

        kwargs = {'chat_id': user.id,
                  'reply_parameters': reply_parameters}
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=kbtext, callback_data=f'kbmessage;{real_message.id}')]])
        types = {
            'text': lambda: bot.send_message(text=text, **kwargs),
            'voice': lambda: bot.send_voice(voice=real_message.file_id, caption=text, **kwargs),
            'sticker': lambda: bot.send_sticker(sticker=real_message.file_id, reply_markup=markup, **kwargs),
            'photo': lambda: bot.send_photo(photo=real_message.file_id, caption=text, **kwargs),
            'video_note': lambda: bot.send_video_note(video_note=real_message.file_id, reply_markup=markup, **kwargs),
            'audio': lambda: bot.send_audio(audio=real_message.file_id, caption=text, **kwargs),
            'video': lambda: bot.send_video(video=real_message.file_id, caption=text, **kwargs),
            'animation': lambda: bot.send_animation(animation=real_message.file_id, caption=text, **kwargs),
            'document': lambda: bot.send_document(document=real_message.file_id, caption=text, **kwargs)
        }

        try:
            message: Message = await types[real_message.type]()
        except:
            return

        fake_message = FakeMessage(id=message.message_id, real_message=real_message, user=user)
        session.add(fake_message)
        session.commit()

    async def save_message(real_message: RealMessage):
        if not real_message.file_id or real_message.type in ['sticker', 'animation']:
            return

        file = await bot.get_file(real_message.file_id)
        path = os.path.join(FILES_PATH, str(real_message.sender_id), real_message.type,
                            os.path.basename(file.file_path))
        await makedirs(os.path.dirname(path), exist_ok=True)
        await bot.download(real_message.file_id, path)

    async def check_message(real_message: RealMessage):
        if not real_message.text:
            return

        track_pairs = get_section('tracked_words/pairs')
        p1 = re.search(f'\\b{'|'.join([f'({word})' for word in track_pairs[0]])}', real_message.text)
        p2 = re.search(f'\\b{'|'.join([f'({word})' for word in track_pairs[1]])}', real_message.text)

        if p1 and p2:
            tasks = []
            for user in session.scalars(select(User)).all():
                if not user.has_opportunity(Opportunity.TRACKED_WORDS_NOTIFICATION):
                    continue

                fake_message = session.scalar(select(FakeMessage)
                                              .where(FakeMessage.real_message == real_message,
                                                     FakeMessage.user == user))
                if fake_message:
                    text = join_strings_at_index('<u>', real_message.text, p1.start())
                    text = join_strings_at_index('</u>', text, p1.end() + 3)
                    text = join_strings_at_index('<u>', text, p2.start() + 3 + 4)
                    text = join_strings_at_index('</u>', text, p2.end() + 3 + 4 + 3)

                    tasks += [notif_bot.send_message(user.id,
                                                     f'<b>Замечено подозрительное сообщение</b>\n\n'
                                                     f'{text}\n\n'
                                                     f'{real_message.sender.role} №{real_message.sender.fake_id}',
                                                     reply_markup=InlineKeyboardMarkup(
                                                         inline_keyboard=[[InlineKeyboardButton(
                                                             text='Выдать предупреждение',
                                                             url=f't.me/{BOT_NAME}?start=warn-{real_message.sender_id}')]]))]
            await gather(*tasks)

    tasks = []
    if real_message.target:
        tasks += [send(real_message, target)]

        for user in session.scalars(select(User).where(User.id != sender.id, User.id != target.id)):
            if user.has_opportunity(Opportunity.READ_PRIVATE_MESSAGES):
                tasks += [send(real_message, user)]
    else:
        for user in session.scalars(select(User).where(User.id != sender.id)):
            tasks += [send(real_message, user)]

    await gather(*tasks)
    create_task(save_message(real_message))
    create_task(check_message(real_message))
    logger.debug(f'Message sent within {(time.time() - debug_time) * 1000} ms')


@router.callback_query(F.data.split(';')[0] == 'kbmessage')
async def kbmessage(callback: CallbackQuery):
    id = int(callback.data.split(';')[1])
    real_message = session.scalar(select(RealMessage).where(RealMessage.id == id))
    text = get_section('id/display').format(real_message.sender)
    await callback.answer(text)


@router.message()
async def unregistered_message(message: Message):
    await bot.send_message(message.from_user.id, 'Вы не зарегистрированы. Пожалуйста введите /start')
