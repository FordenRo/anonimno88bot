from asyncio import sleep, create_task

from aiogram.types import Message


class DelayedMessage:
	def __init__(self, message: Message, delay: int):
		self.message = message
		self.delay = delay

	def start(self):
		async def task(message: DelayedMessage):
			await sleep(message.delay)
			try:
				await message.message.delete()
			except:
				pass

		return create_task(task(self))