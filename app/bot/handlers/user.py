"""Хендлери для клієнтів: меню, запис, мої записи, налаштування."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ...database import session_scope
from ...models import STATUS_PENDING, Booking, Service
from ...services import (
    available_dates,
    available_times,
    create_booking,
    get_or_create_bot_user,
    get_setting,
    human_date,
    is_admin,
    slot_is_free,
    user_bookings,
)
from .. import keyboards as kb
from ..states import BookingFlow, ProfileFlow
from ..utils import booking_line, notify_admins, safe_edit

router = Router()


def _greeting(db, business: str) -> str:
    welcome = get_setting(db, "bot_welcome", "Вітаємо! 💄")
    try:
        return welcome.format(business=business)
    except (KeyError, IndexError):
        return welcome


# ─────────────────────────── /start, /help ───────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    with session_scope() as db:
        business = get_setting(db, "business_name", "GlowStudio")
        user = get_or_create_bot_user(
            db,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
        admin = is_admin(db, message.from_user.id, message.from_user.username)
        if admin and user.role != "admin":
            user.role = "admin"
        text = _greeting(db, business)
    await message.answer(text, reply_markup=kb.main_menu(admin))


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ <b>Як користуватися ботом</b>\n\n"
        "📝 <b>Записатися</b> — оберіть послугу, дату та час.\n"
        "🗓 <b>Мої записи</b> — перегляд і скасування записів.\n"
        "⚙️ <b>Налаштування</b> — телефон та сповіщення.\n\n"
        "Команди: /start, /menu, /help",
        reply_markup=kb.back_home_kb(),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    with session_scope() as db:
        admin = is_admin(db, message.from_user.id, message.from_user.username)
    await message.answer("🏠 Головне меню", reply_markup=kb.main_menu(admin))


@router.callback_query(F.data == "menu:home")
async def back_home(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    with session_scope() as db:
        admin = is_admin(db, cb.from_user.id, cb.from_user.username)
    await safe_edit(cb, "🏠 Головне меню\nОберіть дію 👇", kb.main_menu(admin))
    await cb.answer()


@router.callback_query(F.data == "menu:help")
async def menu_help(cb: CallbackQuery):
    await safe_edit(
        cb,
        "ℹ️ <b>Як користуватися ботом</b>\n\n"
        "📝 Записатися — оберіть послугу, дату та час.\n"
        "🗓 Мої записи — перегляд і скасування.\n"
        "⚙️ Налаштування — телефон та сповіщення.",
        kb.back_home_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "menu:services")
async def menu_services(cb: CallbackQuery):
    with session_scope() as db:
        services = db.query(Service).filter(Service.active == True).order_by(Service.sort_order).all()  # noqa: E712
        lines = ["💄 <b>Наші послуги</b>\n"]
        for s in services:
            lines.append(f"{s.emoji} <b>{s.name}</b> — {int(s.price)}₴ · {s.duration_min} хв\n   <i>{s.description}</i>")
        text = "\n".join(lines) if services else "Послуги поки не додані."
    await safe_edit(cb, text, kb.back_home_kb())
    await cb.answer()


# ─────────────────────────── Запис на сеанс ───────────────────────────
@router.callback_query(F.data == "menu:book")
async def book_start(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    with session_scope() as db:
        services = db.query(Service).filter(Service.active == True).order_by(Service.sort_order).all()  # noqa: E712
        if not services:
            await safe_edit(cb, "На жаль, зараз немає доступних послуг 😔", kb.back_home_kb())
            await cb.answer()
            return
        markup = kb.services_kb(services)
    await state.set_state(BookingFlow.service)
    await safe_edit(cb, "💄 <b>Крок 1/3.</b> Оберіть послугу:", markup)
    await cb.answer()


@router.callback_query(F.data.startswith("book:svc:"))
async def book_pick_service(cb: CallbackQuery, state: FSMContext):
    service_id = int(cb.data.split(":")[2])
    with session_scope() as db:
        service = db.get(Service, service_id)
        if not service:
            await cb.answer("Послугу не знайдено", show_alert=True)
            return
        name = service.name
        dates = available_dates(db)
        markup = kb.dates_kb(dates, 0)
    await state.update_data(service_id=service_id, service_name=name)
    await state.set_state(BookingFlow.date)
    await safe_edit(cb, f"✅ Послуга: <b>{name}</b>\n\n📅 <b>Крок 2/3.</b> Оберіть дату:", markup)
    await cb.answer()


@router.callback_query(F.data.startswith("book:datepage:"))
async def book_date_page(cb: CallbackQuery):
    page = int(cb.data.split(":")[2])
    with session_scope() as db:
        dates = available_dates(db)
    await safe_edit(cb, "📅 <b>Крок 2/3.</b> Оберіть дату:", kb.dates_kb(dates, page))
    await cb.answer()


@router.callback_query(F.data == "book:back:svc")
async def book_back_to_services(cb: CallbackQuery, state: FSMContext):
    await book_start(cb, state)


@router.callback_query(F.data.startswith("book:date:"))
async def book_pick_date(cb: CallbackQuery, state: FSMContext):
    day = cb.data.split(":", 2)[2]
    with session_scope() as db:
        times = available_times(db, day)
    if not times:
        await cb.answer("На цю дату немає вільних слотів 😔", show_alert=True)
        return
    await state.update_data(date=day)
    await state.set_state(BookingFlow.time)
    await safe_edit(cb, f"📅 Дата: <b>{human_date(day)}</b>\n\n🕒 <b>Крок 3/3.</b> Оберіть час:", kb.times_kb(times))
    await cb.answer()


@router.callback_query(F.data == "book:back:date")
async def book_back_to_dates(cb: CallbackQuery, state: FSMContext):
    with session_scope() as db:
        dates = available_dates(db)
    await state.set_state(BookingFlow.date)
    await safe_edit(cb, "📅 <b>Крок 2/3.</b> Оберіть дату:", kb.dates_kb(dates, 0))
    await cb.answer()


@router.callback_query(F.data.startswith("book:time:"))
async def book_pick_time(cb: CallbackQuery, state: FSMContext):
    time = cb.data.split(":", 2)[2]
    data = await state.get_data()
    await state.update_data(time=time)
    await state.set_state(BookingFlow.note)
    summary = (
        "🧾 <b>Перевірте запис</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"💄 Послуга: <b>{data.get('service_name')}</b>\n"
        f"📅 Дата: <b>{human_date(data.get('date'))}</b>\n"
        f"🕒 Час: <b>{time}</b>"
    )
    await safe_edit(cb, summary, kb.confirm_kb())
    await cb.answer()


@router.callback_query(F.data == "book:addnote")
async def book_add_note(cb: CallbackQuery, state: FSMContext):
    await safe_edit(cb, "💬 Напишіть коментар до запису (наприклад, привід чи побажання):")
    await cb.answer()


@router.message(BookingFlow.note)
async def book_note_text(message: Message, state: FSMContext):
    await state.update_data(note=message.text.strip())
    data = await state.get_data()
    summary = (
        "🧾 <b>Перевірте запис</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"💄 Послуга: <b>{data.get('service_name')}</b>\n"
        f"📅 Дата: <b>{human_date(data.get('date'))}</b>\n"
        f"🕒 Час: <b>{data.get('time')}</b>\n"
        f"💬 Коментар: {data.get('note')}"
    )
    await message.answer(summary, reply_markup=kb.confirm_kb())


@router.callback_query(F.data == "book:confirm")
async def book_confirm(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    day, time = data.get("date"), data.get("time")
    if not day or not time:
        await cb.answer("Сесія застаріла, почніть спочатку", show_alert=True)
        await state.clear()
        return
    with session_scope() as db:
        if not slot_is_free(db, day, time):
            await cb.answer("Цей час щойно зайняли 😔 Оберіть інший.", show_alert=True)
            await state.clear()
            return
        user = get_or_create_bot_user(db, cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
        booking = create_booking(
            db, user=user, service_id=data.get("service_id"), day=day, time=time,
            note=data.get("note", ""), source="bot",
        )
        booking_id = booking.id
        svc_name = data.get("service_name")
        client_name = user.full_name
        admin_text = (
            f"🆕 <b>Нове замовлення #{booking_id}</b>\n"
            f"💄 {svc_name}\n"
            f"📅 {human_date(day)} о {time}\n"
            f"👤 {client_name}"
            + (f" (@{cb.from_user.username})" if cb.from_user.username else "")
        )
        await notify_admins(cb.bot, db, admin_text)
    await state.clear()
    await safe_edit(
        cb,
        "🎉 <b>Дякуємо! Ваш запис створено.</b>\n\n"
        f"💄 {svc_name}\n📅 {human_date(day)} о {time}\n\n"
        "Адміністратор підтвердить його найближчим часом. ✅",
        kb.back_home_kb(),
    )
    await cb.answer("Запис створено! 🎉")


# ─────────────────────────── Мої записи ───────────────────────────
@router.callback_query(F.data == "menu:my")
async def my_bookings(cb: CallbackQuery):
    with session_scope() as db:
        user = get_or_create_bot_user(db, cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
        bookings = user_bookings(db, user.id)
        if not bookings:
            await safe_edit(cb, "🗓 У вас ще немає записів.\nНатисніть «Записатися», щоб створити перший. 💄", kb.back_home_kb())
            await cb.answer()
            return
        lines = ["🗓 <b>Ваші записи</b>\n"]
        for b in bookings:
            lines.append(booking_line(b))
        markup = kb.my_bookings_kb(bookings)
        text = "\n".join(lines)
    await safe_edit(cb, text, markup)
    await cb.answer()


@router.callback_query(F.data.startswith("my:cancel:"))
async def my_cancel(cb: CallbackQuery):
    booking_id = int(cb.data.split(":")[2])
    with session_scope() as db:
        user = get_or_create_bot_user(db, cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
        b = db.get(Booking, booking_id)
        if not b or b.user_id != user.id:
            await cb.answer("Запис не знайдено", show_alert=True)
            return
        b.status = "cancelled"
        admin_text = f"❌ Клієнт {user.full_name} скасував запис #{booking_id}"
        await notify_admins(cb.bot, db, admin_text)
        bookings = user_bookings(db, user.id)
        lines = ["🗓 <b>Ваші записи</b>\n"] + [booking_line(x) for x in bookings]
        markup = kb.my_bookings_kb(bookings)
        text = "\n".join(lines)
    await safe_edit(cb, text, markup)
    await cb.answer("Запис скасовано")


# ─────────────────────────── Налаштування ───────────────────────────
async def _render_settings(cb: CallbackQuery):
    with session_scope() as db:
        user = get_or_create_bot_user(db, cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
        text = (
            "⚙️ <b>Налаштування</b>\n\n"
            f"👤 Імʼя: <b>{user.full_name}</b>\n"
            f"📱 Телефон: <b>{user.phone or 'не вказано'}</b>\n"
            f"🔔 Сповіщення: <b>{'увімкнені' if user.notify else 'вимкнені'}</b>"
        )
        markup = kb.settings_kb(user.notify, bool(user.phone))
    await safe_edit(cb, text, markup)


@router.callback_query(F.data == "menu:settings")
async def menu_settings(cb: CallbackQuery):
    await _render_settings(cb)
    await cb.answer()


@router.callback_query(F.data == "set:notify")
async def toggle_notify(cb: CallbackQuery):
    with session_scope() as db:
        user = get_or_create_bot_user(db, cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
        user.notify = not user.notify
    await _render_settings(cb)
    await cb.answer("Готово")


@router.callback_query(F.data == "set:phone")
async def ask_phone(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileFlow.phone)
    await safe_edit(cb, "📱 Надішліть ваш номер телефону у відповідь повідомленням:")
    await cb.answer()


@router.message(ProfileFlow.phone)
async def save_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    with session_scope() as db:
        user = get_or_create_bot_user(db, message.from_user.id, message.from_user.username, message.from_user.full_name)
        user.phone = phone
        admin = is_admin(db, message.from_user.id, message.from_user.username)
    await state.clear()
    await message.answer(f"✅ Телефон збережено: <b>{phone}</b>", reply_markup=kb.main_menu(admin))
