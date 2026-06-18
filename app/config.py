"""Конфігурація застосунку. Значення читаються з файлу `.env`."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")


def _parse_usernames(raw: str) -> set[str]:
    return {u.strip().lstrip("@").lower() for u in raw.split(",") if u.strip()}


def _parse_ids(raw: str) -> set[int]:
    out = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
    BUSINESS_NAME: str = os.getenv("BUSINESS_NAME", "GlowStudio")

    # Адміни з .env (можна один або багато). Доповнюються списком з БД.
    ADMIN_USERNAMES: set[str] = _parse_usernames(os.getenv("ADMIN_USERNAMES", ""))
    ADMIN_IDS: set[int] = _parse_ids(os.getenv("ADMIN_IDS", ""))

    DB_URL: str = f"sqlite:///{DATA_DIR / 'glowcrm.sqlite3'}"


settings = Settings()
