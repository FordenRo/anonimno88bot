from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data == 'hide')
async def hide(callback: CallbackQuery):
	await callback.message.delete()


@router.callback_query(F.data == 'cancel')
async def cancel(callback: CallbackQuery, state: FSMContext):
	await state.clear()
	await callback.message.delete()
