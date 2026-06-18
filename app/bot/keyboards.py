"""Інлайн-клавіатури бота (з яскравими кольоровими кнопками-емодзі)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..models import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_CONFIRMED,
    STATUS_PENDING,
)
from ..services import WEEKDAYS_UA, human_date

DATE_PAGE = 8


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─────────────────────────── Користувач ───────────────────────────
def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📝 Записатися на сеанс", callback_data="menu:book")],
        [
            InlineKeyboardButton(text="🗓 Мої записи", callback_data="menu:my"),
            InlineKeyboardButton(text="💄 Послуги та ціни", callback_data="menu:services"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Налаштування", callback_data="menu:settings"),
            InlineKeyboardButton(text="ℹ️ Допомога", callback_data="menu:help"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Адмін-панель", callback_data="adm:menu")])
    return _kb(rows)


def services_kb(services) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in services:
        b.button(text=f"{s.emoji} {s.name} · {int(s.price)}₴", callback_data=f"book:svc:{s.id}")
    b.button(text="⬅️ Назад", callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def dates_kb(dates: list[str], page: int = 0) -> InlineKeyboardMarkup:
    start = page * DATE_PAGE
    chunk = dates[start:start + DATE_PAGE]
    b = InlineKeyboardBuilder()
    for d in chunk:
        b.button(text=f"📅 {human_date(d)}", callback_data=f"book:date:{d}")
    b.adjust(2)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Раніше", callback_data=f"book:datepage:{page-1}"))
    if start + DATE_PAGE < len(dates):
        nav.append(InlineKeyboardButton(text="Пізніше ▶️", callback_data=f"book:datepage:{page+1}"))
    markup = b.as_markup()
    if nav:
        markup.inline_keyboard.append(nav)
    markup.inline_keyboard.append([InlineKeyboardButton(text="🔙 До послуг", callback_data="book:back:svc")])
    return markup


def times_kb(times: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in times:
        b.button(text=f"🕒 {t}", callback_data=f"book:time:{t}")
    b.adjust(3)
    markup = b.as_markup()
    markup.inline_keyboard.append([InlineKeyboardButton(text="🔙 До дат", callback_data="book:back:date")])
    return markup


def confirm_kb() -> InlineKeyboardMarkup:
    return _kb([
        [InlineKeyboardButton(text="✅ Підтвердити запис", callback_data="book:confirm")],
        [InlineKeyboardButton(text="💬 Додати коментар", callback_data="book:addnote")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="menu:home")],
    ])


def my_bookings_kb(bookings) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for bk in bookings:
        if bk.status in (STATUS_PENDING, STATUS_CONFIRMED):
            b.button(text=f"❌ Скасувати {bk.date} {bk.time}", callback_data=f"my:cancel:{bk.id}")
    b.adjust(1)
    markup = b.as_markup()
    markup.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Головне меню", callback_data="menu:home")])
    return markup


def settings_kb(notify: bool, has_phone: bool) -> InlineKeyboardMarkup:
    notify_label = "🔔 Сповіщення: УВІМК" if notify else "🔕 Сповіщення: ВИМК"
    phone_label = "📱 Змінити телефон" if has_phone else "📱 Додати телефон"
    return _kb([
        [InlineKeyboardButton(text=notify_label, callback_data="set:notify")],
        [InlineKeyboardButton(text=phone_label, callback_data="set:phone")],
        [InlineKeyboardButton(text="⬅️ Головне меню", callback_data="menu:home")],
    ])


def back_home_kb() -> InlineKeyboardMarkup:
    return _kb([[InlineKeyboardButton(text="⬅️ Головне меню", callback_data="menu:home")]])


# ─────────────────────────── Адмін ───────────────────────────
def admin_menu_kb(pending: int = 0) -> InlineKeyboardMarkup:
    orders_label = f"📥 Замовлення ({pending})" if pending else "📥 Замовлення"
    return _kb([
        [InlineKeyboardButton(text=orders_label, callback_data="adm:orders:pending:0")],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats"),
            InlineKeyboardButton(text="👥 Клієнти", callback_data="adm:clients:0"),
        ],
        [
            InlineKeyboardButton(text="💄 Послуги", callback_data="adm:svc:list"),
            InlineKeyboardButton(text="🗓 Графік", callback_data="adm:sched"),
        ],
        [
            InlineKeyboardButton(text="📣 Розсилка", callback_data="adm:bcast"),
            InlineKeyboardButton(text="💬 Привітання", callback_data="adm:welcome"),
        ],
        [InlineKeyboardButton(text="👑 Адміністратори", callback_data="adm:admins")],
        [InlineKeyboardButton(text="⬅️ Вийти в меню", callback_data="menu:home")],
    ])


_STATUS_TABS = [
    (STATUS_PENDING, "🆕 Нові"),
    (STATUS_CONFIRMED, "✅ Підтв."),
    (STATUS_COMPLETED, "🏁 Викон."),
    (STATUS_CANCELLED, "❌ Скас."),
]


def orders_kb(bookings, status: str, page: int, has_more: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for bk in bookings:
        svc = bk.service.emoji if bk.service else "💄"
        b.button(
            text=f"{svc} {bk.date} {bk.time} · {bk.user.full_name[:18]}",
            callback_data=f"adm:order:{bk.id}",
        )
    b.adjust(1)
    markup = b.as_markup()

    tabs = [
        InlineKeyboardButton(
            text=("• " + lbl + " •") if st == status else lbl,
            callback_data=f"adm:orders:{st}:0",
        )
        for st, lbl in _STATUS_TABS
    ]
    markup.inline_keyboard.append(tabs[:2])
    markup.inline_keyboard.append(tabs[2:])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm:orders:{status}:{page-1}"))
    if has_more:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm:orders:{status}:{page+1}"))
    if nav:
        markup.inline_keyboard.append(nav)
    markup.inline_keyboard.append([InlineKeyboardButton(text="🔙 Адмін-панель", callback_data="adm:menu")])
    return markup


def order_detail_kb(booking) -> InlineKeyboardMarkup:
    rows = []
    if booking.status == STATUS_PENDING:
        rows.append([
            InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"adm:order:{booking.id}:confirm"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"adm:order:{booking.id}:cancel"),
        ])
    elif booking.status == STATUS_CONFIRMED:
        rows.append([
            InlineKeyboardButton(text="🏁 Виконано", callback_data=f"adm:order:{booking.id}:complete"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data=f"adm:order:{booking.id}:cancel"),
        ])
    rows.append([InlineKeyboardButton(text="🗑 Видалити", callback_data=f"adm:order:{booking.id}:delete")])
    rows.append([InlineKeyboardButton(text="🔙 До списку", callback_data="adm:orders:pending:0")])
    return _kb(rows)


def admin_services_kb(services) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in services:
        dot = "🟢" if s.active else "⚪️"
        b.button(text=f"{dot} {s.emoji} {s.name} · {int(s.price)}₴", callback_data=f"adm:svc:{s.id}")
    b.adjust(1)
    markup = b.as_markup()
    markup.inline_keyboard.append([InlineKeyboardButton(text="➕ Додати послугу", callback_data="adm:svc:add")])
    markup.inline_keyboard.append([InlineKeyboardButton(text="🔙 Адмін-панель", callback_data="adm:menu")])
    return markup


def service_actions_kb(service) -> InlineKeyboardMarkup:
    toggle = "⚪️ Вимкнути" if service.active else "🟢 Увімкнути"
    return _kb([
        [InlineKeyboardButton(text=toggle, callback_data=f"adm:svc:{service.id}:toggle")],
        [InlineKeyboardButton(text="🗑 Видалити", callback_data=f"adm:svc:{service.id}:del")],
        [InlineKeyboardButton(text="🔙 До послуг", callback_data="adm:svc:list")],
    ])


def schedule_kb(working_days: list[int]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, name in enumerate(WEEKDAYS_UA):
        on = i in working_days
        b.button(text=f"{'🟢' if on else '⚪️'} {name}", callback_data=f"adm:day:{i}")
    b.adjust(4)
    markup = b.as_markup()
    markup.inline_keyboard.append([
        InlineKeyboardButton(text="🕘 Початок", callback_data="adm:sched:start"),
        InlineKeyboardButton(text="🕖 Кінець", callback_data="adm:sched:end"),
    ])
    markup.inline_keyboard.append([
        InlineKeyboardButton(text="⏱ Крок слоту", callback_data="adm:sched:step"),
        InlineKeyboardButton(text="📆 Горизонт", callback_data="adm:sched:horizon"),
    ])
    markup.inline_keyboard.append([InlineKeyboardButton(text="🔙 Адмін-панель", callback_data="adm:menu")])
    return markup


def clients_kb(clients, page: int, has_more: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in clients:
        b.button(text=f"👤 {c.full_name[:24]}", callback_data=f"adm:client:{c.id}")
    b.adjust(1)
    markup = b.as_markup()
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm:clients:{page-1}"))
    if has_more:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm:clients:{page+1}"))
    if nav:
        markup.inline_keyboard.append(nav)
    markup.inline_keyboard.append([InlineKeyboardButton(text="🔙 Адмін-панель", callback_data="adm:menu")])
    return markup


def client_detail_kb(client_id: int) -> InlineKeyboardMarkup:
    return _kb([[InlineKeyboardButton(text="🔙 До клієнтів", callback_data="adm:clients:0")]])


def admins_kb(db_usernames: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for u in db_usernames:
        b.button(text=f"🗑 @{u}", callback_data=f"adm:admin:del:{u}")
    b.adjust(1)
    markup = b.as_markup()
    markup.inline_keyboard.append([InlineKeyboardButton(text="➕ Додати адміна", callback_data="adm:admin:add")])
    markup.inline_keyboard.append([InlineKeyboardButton(text="🔙 Адмін-панель", callback_data="adm:menu")])
    return markup


def admin_back_kb() -> InlineKeyboardMarkup:
    return _kb([[InlineKeyboardButton(text="🔙 Адмін-панель", callback_data="adm:menu")]])
