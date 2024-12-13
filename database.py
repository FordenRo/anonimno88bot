from enum import Enum, Flag
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
	pass


class Opportunity(Flag):
	CAN_SEE_USERNAMES = 1
	NO_MESSAGE_DELAY = 2 ** 1
	CAN_RECEIVE_USER_JOINED_BANNED_MESSAGE = 2 ** 2
	DELETE_OTHERS_MESSAGES = 2 ** 3
	NO_DELETE_RESTRICTIONS = 2 ** 4
	NO_CONTENT_PROTECTION = 2 ** 5
	MUTE_BAN_ADMINS = 2 ** 6
	READ_PRIVATE_MESSAGES = 2 ** 7
	SILENT_MUTE_BAN = 2 ** 8
	CAN_SEE_DELETED_MESSAGES = 2 ** 9

	USER = 0
	ADMIN = NO_MESSAGE_DELAY | NO_DELETE_RESTRICTIONS | DELETE_OTHERS_MESSAGES
	MODERATOR = ADMIN | CAN_SEE_USERNAMES | CAN_RECEIVE_USER_JOINED_BANNED_MESSAGE
	OWNER = MODERATOR | NO_CONTENT_PROTECTION | MUTE_BAN_ADMINS | READ_PRIVATE_MESSAGES | SILENT_MUTE_BAN | CAN_SEE_DELETED_MESSAGES


class AdminPanelOpportunity(Flag):
	CAN_SET_ROLES = 1
	USER_LIST_ACCESS = 2 ** 1
	BAN_LIST_ACCESS = 2 ** 2
	MUTE_LIST_ACCESS = 2 ** 3
	STATISTICS_ACCESS = 2 ** 4
	BOT_BAN_LIST_ACCESS = 2 ** 5
	SERVER_ACCESS = 2 ** 6
	POST_UPDATE = 2 ** 7
	REPORT_LIST = 2 ** 8

	USER = 0
	ADMIN = 0
	MODERATOR = ADMIN | BAN_LIST_ACCESS | MUTE_LIST_ACCESS | BOT_BAN_LIST_ACCESS | REPORT_LIST | STATISTICS_ACCESS | USER_LIST_ACCESS
	OWNER = MODERATOR | CAN_SET_ROLES | SERVER_ACCESS | POST_UPDATE


class CommandOpportunity(Flag):
	user_profile = 1
	panel = 2 ** 1
	toggle_status = 2 ** 2
	warn = 2 ** 3

	USER = 0
	ADMIN = warn
	MODERATOR = ADMIN | user_profile | panel | toggle_status
	OWNER = MODERATOR


class Role(Enum):
	USER = 0
	ADMIN = 1
	OWNER = 2
	MODERATOR = 3

	def __str__(self):
		values = {Role.USER: 'Пользователь',
				  Role.ADMIN: 'Админ',
				  Role.OWNER: 'Создатель',
				  Role.MODERATOR: 'Модератор'}
		return values[self]


class User(Base):
	__tablename__ = 'users'

	id: Mapped[int] = mapped_column(primary_key=True)
	fake_id: Mapped[int] = mapped_column()
	role: Mapped['Role'] = mapped_column(default=Role.USER)
	joined_time: Mapped[int] = mapped_column()
	ban: Mapped['Ban'] = relationship(back_populates='user', primaryjoin='User.id == Ban.user_id')
	mute: Mapped['Mute'] = relationship(back_populates='user', primaryjoin='User.id == Mute.user_id')
	warns: Mapped[list['Warn']] = relationship(back_populates='user', primaryjoin='User.id == Warn.user_id')
	real_messages: Mapped[list['RealMessage']] = relationship(back_populates='sender', foreign_keys='RealMessage.sender_id')
	fake_messages: Mapped[list['FakeMessage']] = relationship(back_populates='user')
	last_message_time: dict[str, int] = {}
	last_id_reset_time: int = 0
	last_delete_time: int = 0

	private_with_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=True)
	private_with: Mapped[Optional['User']] = relationship(remote_side=id)

	@hybrid_property
	def opportunities(self):
		return Opportunity(Opportunity[self.role.name])

	@hybrid_property
	def command_opportunities(self):
		return CommandOpportunity(CommandOpportunity[self.role.name])

	@hybrid_property
	def admin_panel_opportunities(self):
		return AdminPanelOpportunity(AdminPanelOpportunity[self.role.name])

	def has_opportunity(self, opportunity: Opportunity):
		return opportunity in self.opportunities

	def has_command_opportunity(self, opportunity: CommandOpportunity):
		return opportunity in self.command_opportunities

	def has_admin_panel_opportunity(self, opportunity: AdminPanelOpportunity):
		return opportunity in self.admin_panel_opportunities

	def get_last_message_time(self, type: str):
		return self.last_message_time.get(type) or 0


class RealMessage(Base):
	__tablename__ = 'real_messages'

	id: Mapped[int] = mapped_column(primary_key=True)
	time: Mapped[int] = mapped_column()
	type: Mapped[str] = mapped_column()
	text: Mapped[str] = mapped_column(nullable=True)
	file_id: Mapped[str] = mapped_column(nullable=True)
	fake_messages: Mapped[list['FakeMessage']] = relationship(back_populates='real_message')

	reply_to_id: Mapped[int] = mapped_column(ForeignKey('real_messages.id'), nullable=True)
	reply_to: Mapped[Optional['RealMessage']] = relationship()

	sender_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
	sender: Mapped['User'] = relationship(back_populates='real_messages', foreign_keys=[sender_id])

	target_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=True)
	target: Mapped[Optional['User']] = relationship(foreign_keys=[target_id])


class FakeMessage(Base):
	__tablename__ = 'fake_messages'

	id: Mapped[int] = mapped_column(primary_key=True)

	real_message_id: Mapped[int] = mapped_column(ForeignKey('real_messages.id'))
	real_message: Mapped['RealMessage'] = relationship(back_populates='fake_messages')

	user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
	user: Mapped['User'] = relationship(back_populates='fake_messages')


class Ban(Base):
	__tablename__ = 'bans'

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	time: Mapped[int] = mapped_column()
	duration: Mapped[int] = mapped_column()

	user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
	user: Mapped['User'] = relationship(back_populates='ban', foreign_keys=[user_id])

	sender_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
	sender: Mapped['User'] = relationship(foreign_keys=[sender_id])


class Mute(Base):
	__tablename__ = 'mutes'

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	time: Mapped[int] = mapped_column()
	duration: Mapped[int] = mapped_column()

	user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
	user: Mapped['User'] = relationship(back_populates='mute', foreign_keys=[user_id])

	sender_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
	sender: Mapped['User'] = relationship(foreign_keys=[sender_id])


class Warn(Base):
	__tablename__ = 'warns'

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	time: Mapped[int] = mapped_column()
	section: Mapped[int] = mapped_column()

	user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
	user: Mapped['User'] = relationship(back_populates='warns', foreign_keys=[user_id])

	sender_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
	sender: Mapped['User'] = relationship(foreign_keys=[sender_id])
