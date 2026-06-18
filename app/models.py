"""Моделі бази даних GlowCRM."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Статуси записів
STATUS_PENDING = "pending"        # 🆕 новий, очікує підтвердження
STATUS_CONFIRMED = "confirmed"    # ✅ підтверджено
STATUS_COMPLETED = "completed"    # 🏁 виконано
STATUS_CANCELLED = "cancelled"    # ❌ скасовано

STATUS_LABELS = {
    STATUS_PENDING: "Новий",
    STATUS_CONFIRMED: "Підтверджено",
    STATUS_COMPLETED: "Виконано",
    STATUS_CANCELLED: "Скасовано",
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | admin
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    duration_min: Mapped[int] = mapped_column(Integer, default=60)
    price: Mapped[float] = mapped_column(Float, default=0)
    color: Mapped[str] = mapped_column(String(20), default="#f472b6")
    emoji: Mapped[str] = mapped_column(String(10), default="💄")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="service")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("services.id"), nullable=True)
    date: Mapped[str] = mapped_column(String(10))   # YYYY-MM-DD
    time: Mapped[str] = mapped_column(String(5))     # HH:MM
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING)
    note: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="bot")  # bot | admin
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="bookings")
    service: Mapped[Optional["Service"]] = relationship(back_populates="bookings")


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Setting(Base):
    """Просте сховище ключ-значення для бізнес-налаштувань та конфігурації бота."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")

    def as_obj(self):
        try:
            return json.loads(self.value)
        except (ValueError, TypeError):
            return self.value
