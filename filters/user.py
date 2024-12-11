from aiogram.filters import Filter
from aiogram.types import Message
from sqlalchemy import select

from database import User
from globals import session


class UserFilter(Filter):
	async def __call__(self, message: Message) -> bool | dict[str, any]:
		user = session.scalar(select(User).where(User.id == message.from_user.id))
		if not user:
			return False

		return {'user': user}
