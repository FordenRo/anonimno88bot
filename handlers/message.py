import time

from aiogram import Router
from aiogram.types import Message, ReplyParameters
from sqlalchemy import select

from database import User, RealMessage, FakeMessage, Opportunity, DelayedMessage
from filters.user import UserFilter
from globals import session, bot, start_time
from utils import get_string, time_to_str

router = Router()


@router.message(UserFilter())
async def message(message: Message, user: User):
	sender = user
	text = message.text or message.caption
	content_type = message.content_type.name.lower()
	file_id = getattr(getattr(message, content_type), 'file_id', None)
	reply_to = None
	current_time = int(time.time())

	debounce = get_string(f'debounce/{content_type}/delay')
	remaining_time = int(sender.get_last_message_time(content_type) + debounce - current_time)
	if (current_time > start_time + 5
			and remaining_time > 0
			and not sender.has_opportunity(Opportunity.NO_MESSAGE_DELAY)):
		await message.delete()
		message = await bot.send_message(sender.id, get_string(f'debounce/{content_type}/message')
										 .format(time_to_str(remaining_time)))
		session.add(DelayedMessage(message_id=message.message_id, chat_id=sender.id, delay=2))
		session.commit()
		return

	if message.reply_to_message:
		reply_to = getattr(
			session.scalar(select(FakeMessage).where(FakeMessage.id == message.reply_to_message.message_id)),
			'real_message',
			session.scalar(select(RealMessage).where(RealMessage.id == message.reply_to_message.message_id)))

	user.last_message_time[content_type] = current_time
	real_message = RealMessage(id=message.message_id, sender=sender, type=content_type, text=text,
							   file_id=file_id, reply_to=reply_to, time=current_time)
	session.add(real_message)
	session.commit()

	for user in session.scalars(select(User).where(User.id != sender.id)):
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
		types = {
			'text': lambda: bot.send_message(text=text, **kwargs),
			'voice': lambda: bot.send_voice(voice=real_message.file_id, caption=text, **kwargs),
			'sticker': lambda: bot.send_sticker(sticker=real_message.file_id, **kwargs),
			'photo': lambda: bot.send_photo(photo=real_message.file_id, caption=text, **kwargs),
			'video_note': lambda: bot.send_video_note(video_note=real_message.file_id, **kwargs),
			'audio': lambda: bot.send_audio(audio=real_message.file_id, caption=text, **kwargs),
			'video': lambda: bot.send_video(video=real_message.file_id, caption=text, **kwargs),
			'animation': lambda: bot.send_animation(animation=real_message.file_id, caption=text, **kwargs),
			'document': lambda: bot.send_document(document=real_message.file_id, caption=text, **kwargs)
		}
		message: Message = await types[real_message.type]()

		fake_message = FakeMessage(id=message.message_id, real_message=real_message, user=user)
		session.add(fake_message)
		session.commit()
