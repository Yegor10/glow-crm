"""Початкове наповнення бази даних."""
from __future__ import annotations

import json

from .config import settings as cfg
from .database import session_scope
from .models import Service, Setting

DEFAULT_SETTINGS = {
    "business_name": cfg.BUSINESS_NAME,
    "working_days": [0, 1, 2, 3, 4, 5],   # 0=Пн ... 6=Нд
    "work_start": "09:00",
    "work_end": "19:00",
    "slot_step_min": 60,
    "horizon_days": 31,
    "bot_welcome": (
        "Вітаємо у {business}! 💄✨\n\n"
        "Тут ви можете швидко записатися на сеанс макіяжу: оберіть послугу, "
        "зручну дату та час. Скористайтеся кнопками нижче 👇"
    ),
    # Додаткові адміни, додані прямо в боті (username без @).
    "admin_usernames": [],
    "admin_ids": [],
}

DEFAULT_SERVICES = [
    {"name": "Денний макіяж", "description": "Легкий природний образ на щодень.", "duration_min": 60, "price": 800, "color": "#f472b6", "emoji": "🌸"},
    {"name": "Вечірній макіяж", "description": "Виразний образ для особливих подій.", "duration_min": 90, "price": 1200, "color": "#a78bfa", "emoji": "🌙"},
    {"name": "Весільний макіяж", "description": "Стійкий образ нареченої + репетиція.", "duration_min": 120, "price": 2500, "color": "#fb7185", "emoji": "💍"},
    {"name": "Макіяж + зачіска", "description": "Повний образ під ключ.", "duration_min": 150, "price": 2000, "color": "#34d399", "emoji": "💇"},
    {"name": "Урок макіяжу", "description": "Індивідуальне навчання self-make-up.", "duration_min": 120, "price": 1500, "color": "#38bdf8", "emoji": "🎓"},
]


def seed_initial_data():
    with session_scope() as db:
        for key, value in DEFAULT_SETTINGS.items():
            if db.get(Setting, key) is None:
                db.add(Setting(key=key, value=json.dumps(value, ensure_ascii=False)))

        if db.query(Service).count() == 0:
            for i, s in enumerate(DEFAULT_SERVICES):
                db.add(Service(sort_order=i, active=True, **s))
