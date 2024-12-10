from aiogram.filters import Command
from aiogram.filters.command import CommandException
from aiogram.types import Message
from sqlalchemy import select

from database import Opportunity, User, CommandOpportunity
from globals import session


class UserCommand(Command):
	command_list: list['UserCommand'] = []

	def __init__(self, *commands, opportunity: CommandOpportunity = CommandOpportunity.USER, description: str = None,
				 prefix: str = '/'):
		super().__init__(*commands, prefix=prefix)

		self.description = description
		self.opportunity = opportunity

		UserCommand.command_list += [self]

	async def __call__(self, message: Message, bot):
		if not isinstance(message, Message):
			return False

		text = message.text or message.caption
		if not text:
			return False

		try:
			command = await self.parse_command(text=text, bot=bot)
		except CommandException:
			return False

		user: User = session.scalar(select(User).where(User.id == message.from_user.id))
		if not user.has_command_opportunity(self.opportunity):
			return False

		result = {"command": command, 'user': user}
		if command.magic_result and isinstance(command.magic_result, dict):
			result.update(command.magic_result)
		return result
