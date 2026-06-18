"""Допоміжні функції бота: сповіщення та форматування тексту."""
from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from sqlalchemy.orm import Session

from ..models import STATUS_LABELS, Booking, User
from ..services import human_date

STATUS_EMOJI = {
    "pending": "🆕",
    "confirmed": "✅",
    "completed": "🏁",
    "cancelled": "❌",
}


async def safe_edit(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    """Безпечне редагування повідомлення (ігнорує 'message is not modified')."""
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        try:
            await cb.message.answer(text, reply_markup=kb)
        except TelegramBadRequest:
            pass


async def notify_admins(bot: Bot, db: Session, text: str) -> None:
    """Надіслати повідомлення всім адміністраторам, що користувалися ботом."""
    admins = db.query(User).filter(User.role == "admin", User.telegram_id.isnot(None)).all()
    for a in admins:
        try:
            await bot.send_message(a.telegram_id, text)
        except Exception:  # noqa: BLE001
            pass


async def notify_user(bot: Bot, user: User, text: str) -> None:
    if not user or not user.telegram_id or not user.notify:
        return
    try:
        await bot.send_message(user.telegram_id, text)
    except Exception:  # noqa: BLE001
        pass


def booking_line(b: Booking) -> str:
    svc = f"{b.service.emoji} {b.service.name}" if b.service else "💄 Сеанс"
    em = STATUS_EMOJI.get(b.status, "•")
    return f"{em} <b>{human_date(b.date)}</b> о <b>{b.time}</b> — {svc} ({STATUS_LABELS.get(b.status, b.status)})"


def order_card(b: Booking) -> str:
    svc = f"{b.service.emoji} {b.service.name} · {int(b.service.price)}₴" if b.service else "Сеанс"
    uname = f"@{b.user.username}" if b.user and b.user.username else "—"
    phone = b.user.phone if b.user and b.user.phone else "—"
    return (
        f"{STATUS_EMOJI.get(b.status, '•')} <b>Замовлення #{b.id}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💄 Послуга: <b>{svc}</b>\n"
        f"📅 Дата: <b>{human_date(b.date)}</b>\n"
        f"🕒 Час: <b>{b.time}</b>\n"
        f"👤 Клієнт: <b>{b.user.full_name if b.user else '—'}</b> ({uname})\n"
        f"📱 Телефон: {phone}\n"
        f"💬 Коментар: {b.note or '—'}\n"
        f"📌 Статус: <b>{STATUS_LABELS.get(b.status, b.status)}</b>\n"
        f"🔻 Джерело: {b.source}"
    )
