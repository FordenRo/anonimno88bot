import os.path
import time
from asyncio import gather, create_task

from aiofiles.os import makedirs
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyParameters, \
	InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from sqlalchemy import select

from database import User, RealMessage, FakeMessage, Opportunity
from filters.user import UserFilter
from globals import session, bot, START_TIME, FILES_PATH, logger
from handlers.delayed import DelayedMessage
from states.private import PrivateStates
from utils import get_section, time_to_str

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
			text += f'\n{chat.full_name} (@{chat.username})'
			if real_message.target:
				chat = await bot.get_chat(real_message.target.id)
				text += f'\n{chat.full_name} (@{chat.username})'

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
		if real_message.type in ['sticker', 'animation']:
			return

		file = await bot.get_file(real_message.file_id)
		path = os.path.join(FILES_PATH, str(real_message.sender_id), real_message.type,
							os.path.basename(file.file_path))
		await makedirs(os.path.dirname(path), exist_ok=True)
		await bot.download(real_message.file_id, path)

	if real_message.file_id:
		create_task(save_message(real_message))

	tasks = []
	if state == PrivateStates.message:
		target = await state.get_value('target')
		tasks += [send(real_message, target)]

		for user in session.scalars(select(User).where(User.id != sender.id, User.id != target.id)):
			if user.has_opportunity(Opportunity.READ_PRIVATE_MESSAGES):
				tasks += [send(real_message, user)]
	else:
		for user in session.scalars(select(User).where(User.id != sender.id)):
			tasks += [send(real_message, user)]

	await gather(*tasks)
	logger.debug(f'Message sent within {(time.time() - debug_time) * 1000} ms')


@router.callback_query(F.data.split(';')[0] == 'kbmessage')
async def kbmessage(callback: CallbackQuery):
	id = int(callback.data.split(';')[1])
	real_message = session.scalar(select(RealMessage).where(RealMessage.id == id))
	text = get_section('id/display').format(real_message.sender)
	await callback.answer(text)
