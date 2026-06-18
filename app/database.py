"""Налаштування бази даних (SQLite + SQLAlchemy).

Базу спільно використовують і веб-панель, і Telegram-бот, тому вмикаємо
режим WAL для безпечного одночасного доступу з двох процесів.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.DB_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope():
    """Контекстний менеджер для зручної роботи з сесією."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """FastAPI-залежність, що віддає сесію БД."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Створює таблиці та початкові дані."""
    from . import models  # noqa: F401  (реєстрація моделей)
    from .seed import seed_initial_data

    Base.metadata.create_all(bind=engine)
    seed_initial_data()
