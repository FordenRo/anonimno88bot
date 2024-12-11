from typing import Any, Union, Dict

from aiogram.filters import Filter
from aiogram.types import Message
from sqlalchemy import select

from database import User
from globals import session


class UserFilter(Filter):
	def __init__(self):
		pass

	async def __call__(self, message: Message) -> Union[bool, Dict[str, Any]]:
		user = session.scalar(select(User).where(User.id == message.from_user.id))
		if not user:
			return False

		return {'user': user}
