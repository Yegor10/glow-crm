"""Фільтр доступу до адмін-функцій."""
from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from ..database import session_scope
from ..services import is_admin


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        if not user:
            return False
        with session_scope() as db:
            return is_admin(db, user.id, user.username)
