"""Спільна бізнес-логіка: налаштування, генерація слотів, записи, статистика.

Використовується і веб-панеллю, і ботом, щоб логіка була єдиною.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import settings as cfg
from .models import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_CONFIRMED,
    STATUS_PENDING,
    Booking,
    Service,
    Setting,
    User,
)

WEEKDAYS_UA = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
MONTHS_UA = [
    "січня", "лютого", "березня", "квітня", "травня", "червня",
    "липня", "серпня", "вересня", "жовтня", "листопада", "грудня",
]

ACTIVE_STATUSES = (STATUS_PENDING, STATUS_CONFIRMED)


# ─────────────────────────── Налаштування ───────────────────────────
def get_setting(db: Session, key: str, default=None):
    row = db.get(Setting, key)
    if row is None:
        return default
    try:
        return json.loads(row.value)
    except (ValueError, TypeError):
        return row.value


def set_setting(db: Session, key: str, value) -> None:
    row = db.get(Setting, key)
    payload = json.dumps(value, ensure_ascii=False)
    if row is None:
        db.add(Setting(key=key, value=payload))
    else:
        row.value = payload


def get_all_settings(db: Session) -> dict:
    return {row.key: row.as_obj() for row in db.query(Setting).all()}


def get_bot_token() -> str:
    """Токен бота береться з .env (BOT_TOKEN)."""
    return cfg.BOT_TOKEN.strip()


# ─────────────────────────── Адміністратори ───────────────────────────
def is_admin(db: Session, telegram_id: int | None, username: str | None) -> bool:
    """Чи є користувач адміністратором (env-список + список з БД + роль)."""
    uname = (username or "").lstrip("@").lower()
    if telegram_id and telegram_id in cfg.ADMIN_IDS:
        return True
    if uname and uname in cfg.ADMIN_USERNAMES:
        return True
    db_usernames = {u.lower() for u in get_setting(db, "admin_usernames", []) or []}
    db_ids = set(get_setting(db, "admin_ids", []) or [])
    if uname and uname in db_usernames:
        return True
    if telegram_id and telegram_id in db_ids:
        return True
    return False


def add_admin_username(db: Session, username: str) -> None:
    uname = username.lstrip("@").lower()
    current = list(get_setting(db, "admin_usernames", []) or [])
    if uname not in current:
        current.append(uname)
        set_setting(db, "admin_usernames", current)


def remove_admin_username(db: Session, username: str) -> bool:
    uname = username.lstrip("@").lower()
    current = list(get_setting(db, "admin_usernames", []) or [])
    if uname in current:
        current.remove(uname)
        set_setting(db, "admin_usernames", current)
        return True
    return False


def list_admins(db: Session) -> dict:
    return {
        "env_usernames": sorted(cfg.ADMIN_USERNAMES),
        "env_ids": sorted(cfg.ADMIN_IDS),
        "db_usernames": list(get_setting(db, "admin_usernames", []) or []),
        "db_ids": list(get_setting(db, "admin_ids", []) or []),
    }


# ─────────────────────────── Дати та слоти ───────────────────────────
def human_date(d: date | str) -> str:
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    return f"{WEEKDAYS_UA[d.weekday()]}, {d.day} {MONTHS_UA[d.month - 1]}"


def _time_slots(work_start: str, work_end: str, step_min: int) -> list[str]:
    start = datetime.strptime(work_start, "%H:%M")
    end = datetime.strptime(work_end, "%H:%M")
    slots = []
    cur = start
    while cur < end:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return slots


def available_dates(db: Session) -> list[str]:
    """Список доступних дат на найближчий горизонт (робочі дні)."""
    working_days = set(get_setting(db, "working_days", [0, 1, 2, 3, 4, 5]))
    horizon = int(get_setting(db, "horizon_days", 31))
    today = date.today()
    result = []
    for offset in range(horizon):
        d = today + timedelta(days=offset)
        if d.weekday() in working_days:
            result.append(d.isoformat())
    return result


def available_times(db: Session, day: str) -> list[str]:
    """Вільні часові слоти на конкретну дату."""
    work_start = get_setting(db, "work_start", "09:00")
    work_end = get_setting(db, "work_end", "19:00")
    step = int(get_setting(db, "slot_step_min", 60))
    all_slots = _time_slots(work_start, work_end, step)

    taken = {
        b.time
        for b in db.query(Booking).filter(
            Booking.date == day, Booking.status.in_(ACTIVE_STATUSES)
        )
    }
    today_str = date.today().isoformat()
    now_hm = datetime.now().strftime("%H:%M")
    free = []
    for slot in all_slots:
        if slot in taken:
            continue
        if day == today_str and slot <= now_hm:
            continue
        free.append(slot)
    return free


def slot_is_free(db: Session, day: str, time: str) -> bool:
    return time in set(available_times(db, day))


# ─────────────────────────── Користувачі ───────────────────────────
def get_or_create_bot_user(db: Session, telegram_id: int, username: str | None, full_name: str) -> User:
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name or username or "Клієнт",
            role="user",
        )
        db.add(user)
        db.flush()
    else:
        # Оновлюємо актуальні дані профілю Telegram
        if username and user.username != username:
            user.username = username
        if full_name and not user.full_name:
            user.full_name = full_name
    return user


# ─────────────────────────── Записи ───────────────────────────
def create_booking(db: Session, *, user: User, service_id: int | None, day: str,
                    time: str, note: str = "", source: str = "bot") -> Booking | None:
    if not slot_is_free(db, day, time):
        return None
    booking = Booking(
        user_id=user.id,
        service_id=service_id,
        date=day,
        time=time,
        status=STATUS_PENDING,
        note=note,
        source=source,
    )
    db.add(booking)
    db.flush()
    return booking


def user_bookings(db: Session, user_id: int, only_active: bool = False) -> list[Booking]:
    q = db.query(Booking).filter(Booking.user_id == user_id)
    if only_active:
        q = q.filter(Booking.status.in_(ACTIVE_STATUSES))
    return q.order_by(Booking.date, Booking.time).all()


def cancel_booking(db: Session, booking_id: int, user_id: int | None = None) -> bool:
    q = db.query(Booking).filter(Booking.id == booking_id)
    if user_id is not None:
        q = q.filter(Booking.user_id == user_id)
    booking = q.first()
    if booking is None or booking.status == STATUS_CANCELLED:
        return False
    booking.status = STATUS_CANCELLED
    return True


# ─────────────────────────── Статистика ───────────────────────────
def dashboard_stats(db: Session) -> dict:
    today = date.today().isoformat()
    total = db.query(func.count(Booking.id)).scalar() or 0
    pending = db.query(func.count(Booking.id)).filter(Booking.status == STATUS_PENDING).scalar() or 0
    confirmed = db.query(func.count(Booking.id)).filter(Booking.status == STATUS_CONFIRMED).scalar() or 0
    completed = db.query(func.count(Booking.id)).filter(Booking.status == STATUS_COMPLETED).scalar() or 0
    today_count = db.query(func.count(Booking.id)).filter(
        Booking.date == today, Booking.status.in_(ACTIVE_STATUSES)
    ).scalar() or 0
    clients = db.query(func.count(User.id)).filter(User.role == "user").scalar() or 0

    revenue = (
        db.query(func.coalesce(func.sum(Service.price), 0.0))
        .select_from(Booking)
        .join(Service, Booking.service_id == Service.id)
        .filter(Booking.status == STATUS_COMPLETED)
        .scalar()
    ) or 0.0

    # Завантаженість по днях за останні 14 днів
    series = []
    for offset in range(13, -1, -1):
        d = (date.today() - timedelta(days=offset)).isoformat()
        cnt = db.query(func.count(Booking.id)).filter(
            Booking.date == d, Booking.status != STATUS_CANCELLED
        ).scalar() or 0
        series.append({"date": d, "count": cnt})

    return {
        "total": total,
        "pending": pending,
        "confirmed": confirmed,
        "completed": completed,
        "today": today_count,
        "clients": clients,
        "revenue": revenue,
        "series": series,
    }
