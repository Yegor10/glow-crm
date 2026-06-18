"""Адмін-панель прямо в Telegram-боті."""
from __future__ import annotations

import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ...database import session_scope
from ...models import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_CONFIRMED,
    STATUS_LABELS,
    STATUS_PENDING,
    Booking,
    Service,
    User,
)
from ...services import (
    add_admin_username,
    dashboard_stats,
    get_setting,
    human_date,
    list_admins,
    remove_admin_username,
    set_setting,
)
from .. import keyboards as kb
from ..filters import IsAdmin
from ..states import (
    AdminAddAdmin,
    AdminBroadcast,
    AdminSchedule,
    AdminService,
    AdminWelcome,
)
from ..utils import notify_user, order_card, safe_edit

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

PAGE = 6
COLORS = ["#f472b6", "#a78bfa", "#fb7185", "#34d399", "#38bdf8", "#fbbf24", "#f97316"]


def _admin_menu_text(db) -> str:
    business = get_setting(db, "business_name", "GlowStudio")
    return f"🛠 <b>Адмін-панель</b> · {business}\nОберіть розділ для керування 👇"


# ─────────────────────────── Головне меню адміна ───────────────────────────
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    with session_scope() as db:
        pending = db.query(Booking).filter(Booking.status == STATUS_PENDING).count()
        text = _admin_menu_text(db)
    await message.answer(text, reply_markup=kb.admin_menu_kb(pending))


@router.callback_query(F.data == "adm:menu")
async def admin_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    with session_scope() as db:
        pending = db.query(Booking).filter(Booking.status == STATUS_PENDING).count()
        text = _admin_menu_text(db)
    await safe_edit(cb, text, kb.admin_menu_kb(pending))
    await cb.answer()


# ─────────────────────────── Статистика ───────────────────────────
@router.callback_query(F.data == "adm:stats")
async def admin_stats(cb: CallbackQuery):
    with session_scope() as db:
        s = dashboard_stats(db)
        bars = ""
        mx = max((d["count"] for d in s["series"]), default=0) or 1
        for d in s["series"][-7:]:
            filled = round(d["count"] / mx * 8)
            bars += f"\n{d['date'][5:]}  {'▰' * filled}{'▱' * (8 - filled)} {d['count']}"
    text = (
        "📊 <b>Статистика студії</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"🆕 Нові: <b>{s['pending']}</b>\n"
        f"✅ Підтверджені: <b>{s['confirmed']}</b>\n"
        f"🏁 Виконані: <b>{s['completed']}</b>\n"
        f"📅 Сьогодні: <b>{s['today']}</b>\n"
        f"👥 Клієнтів: <b>{s['clients']}</b>\n"
        f"💰 Дохід (виконані): <b>{int(s['revenue'])}₴</b>\n"
        f"\n<b>Завантаженість (7 днів):</b>{bars}"
    )
    await safe_edit(cb, text, kb.admin_back_kb())
    await cb.answer()


# ─────────────────────────── Замовлення ───────────────────────────
@router.callback_query(F.data.startswith("adm:orders:"))
async def admin_orders(cb: CallbackQuery):
    _, _, status, page_s = cb.data.split(":")
    page = int(page_s)
    with session_scope() as db:
        q = db.query(Booking).filter(Booking.status == status).order_by(Booking.date, Booking.time)
        rows = q.offset(page * PAGE).limit(PAGE + 1).all()
        has_more = len(rows) > PAGE
        rows = rows[:PAGE]
        label = STATUS_LABELS.get(status, status)
        if not rows:
            text = f"📥 <b>Замовлення</b> · {label}\n\nНемає замовлень у цьому статусі."
        else:
            text = f"📥 <b>Замовлення</b> · {label}\nОберіть замовлення для деталей 👇"
        markup = kb.orders_kb(rows, status, page, has_more)
    await safe_edit(cb, text, markup)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^adm:order:\d+$"))
async def admin_order_detail(cb: CallbackQuery):
    booking_id = int(cb.data.split(":")[2])
    with session_scope() as db:
        b = db.get(Booking, booking_id)
        if not b:
            await cb.answer("Замовлення не знайдено", show_alert=True)
            return
        text = order_card(b)
        markup = kb.order_detail_kb(b)
    await safe_edit(cb, text, markup)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^adm:order:\d+:(confirm|complete|cancel|delete)$"))
async def admin_order_action(cb: CallbackQuery):
    _, _, bid_s, action = cb.data.split(":")
    booking_id = int(bid_s)
    with session_scope() as db:
        b = db.get(Booking, booking_id)
        if not b:
            await cb.answer("Замовлення не знайдено", show_alert=True)
            return
        if action == "delete":
            db.delete(b)
            await safe_edit(cb, "🗑 Замовлення видалено.", kb.admin_back_kb())
            await cb.answer("Видалено")
            return

        new_status = {
            "confirm": STATUS_CONFIRMED,
            "complete": STATUS_COMPLETED,
            "cancel": STATUS_CANCELLED,
        }[action]
        b.status = new_status
        svc = b.service.name if b.service else "Сеанс"
        msg = {
            STATUS_CONFIRMED: f"✅ Ваш запис підтверджено!\n💄 {svc}\n📅 {human_date(b.date)} о {b.time}",
            STATUS_COMPLETED: f"🏁 Дякуємо за візит!\n💄 {svc}\n📅 {human_date(b.date)}",
            STATUS_CANCELLED: f"❌ Ваш запис скасовано.\n💄 {svc}\n📅 {human_date(b.date)} о {b.time}",
        }[new_status]
        await notify_user(cb.bot, b.user, msg)
        text = order_card(b)
        markup = kb.order_detail_kb(b)
    await safe_edit(cb, text, markup)
    await cb.answer("Статус оновлено ✅")


# ─────────────────────────── Послуги ───────────────────────────
@router.callback_query(F.data == "adm:svc:list")
async def admin_services(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    with session_scope() as db:
        services = db.query(Service).order_by(Service.sort_order, Service.id).all()
        markup = kb.admin_services_kb(services)
    await safe_edit(cb, "💄 <b>Послуги</b>\n🟢 — активна, ⚪️ — прихована", markup)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^adm:svc:\d+$"))
async def admin_service_detail(cb: CallbackQuery):
    sid = int(cb.data.split(":")[2])
    with session_scope() as db:
        s = db.get(Service, sid)
        if not s:
            await cb.answer("Не знайдено", show_alert=True)
            return
        text = (
            f"{s.emoji} <b>{s.name}</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"💰 Ціна: <b>{int(s.price)}₴</b>\n"
            f"⏱ Тривалість: <b>{s.duration_min} хв</b>\n"
            f"📝 {s.description or '—'}\n"
            f"Стан: <b>{'активна 🟢' if s.active else 'прихована ⚪️'}</b>"
        )
        markup = kb.service_actions_kb(s)
    await safe_edit(cb, text, markup)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^adm:svc:\d+:toggle$"))
async def admin_service_toggle(cb: CallbackQuery):
    sid = int(cb.data.split(":")[2])
    with session_scope() as db:
        s = db.get(Service, sid)
        if s:
            s.active = not s.active
    await admin_service_detail(cb)


@router.callback_query(F.data.regexp(r"^adm:svc:\d+:del$"))
async def admin_service_delete(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[2])
    with session_scope() as db:
        s = db.get(Service, sid)
        if s:
            db.delete(s)
        services = db.query(Service).order_by(Service.sort_order, Service.id).all()
        markup = kb.admin_services_kb(services)
    await safe_edit(cb, "🗑 Послугу видалено.\n\n💄 <b>Послуги</b>", markup)
    await cb.answer("Видалено")


@router.callback_query(F.data == "adm:svc:add")
async def admin_service_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminService.name)
    await safe_edit(cb, "➕ <b>Нова послуга</b>\n\nКрок 1/4. Введіть назву послуги:")
    await cb.answer()


@router.message(AdminService.name)
async def svc_add_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminService.price)
    await message.answer("Крок 2/4. Введіть ціну (грн), напр. <b>1200</b>:")


@router.message(AdminService.price)
async def svc_add_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("⚠️ Введіть число, напр. 1200")
        return
    await state.update_data(price=price)
    await state.set_state(AdminService.duration)
    await message.answer("Крок 3/4. Введіть тривалість у хвилинах, напр. <b>60</b>:")


@router.message(AdminService.duration)
async def svc_add_duration(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("⚠️ Введіть ціле число хвилин, напр. 60")
        return
    await state.update_data(duration=int(message.text.strip()))
    await state.set_state(AdminService.emoji)
    await message.answer("Крок 4/4. Надішліть емодзі для послуги (напр. 💋) або «-»:")


@router.message(AdminService.emoji)
async def svc_add_emoji(message: Message, state: FSMContext):
    emoji = message.text.strip()
    if emoji == "-" or not emoji:
        emoji = "💄"
    data = await state.get_data()
    with session_scope() as db:
        order = db.query(Service).count()
        s = Service(
            name=data["name"], price=data["price"], duration_min=data["duration"],
            emoji=emoji[:4], color=random.choice(COLORS), active=True, sort_order=order,
            description="",
        )
        db.add(s)
    await state.clear()
    await message.answer(
        f"✅ Послугу <b>{data['name']}</b> додано!",
        reply_markup=kb.admin_back_kb(),
    )


# ─────────────────────────── Графік роботи ───────────────────────────
async def _render_schedule(target, db):
    days = get_setting(db, "working_days", [])
    names = ", ".join(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"][i] for i in days) or "—"
    text = (
        "🗓 <b>Графік роботи</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"📆 Робочі дні: <b>{names}</b>\n"
        f"🕘 Початок: <b>{get_setting(db, 'work_start', '09:00')}</b>\n"
        f"🕖 Кінець: <b>{get_setting(db, 'work_end', '19:00')}</b>\n"
        f"⏱ Крок слоту: <b>{get_setting(db, 'slot_step_min', 60)} хв</b>\n"
        f"📆 Горизонт запису: <b>{get_setting(db, 'horizon_days', 31)} дн.</b>\n\n"
        "Натисніть на день, щоб увімкнути/вимкнути:"
    )
    return text, kb.schedule_kb(days)


@router.callback_query(F.data == "adm:sched")
async def admin_schedule(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    with session_scope() as db:
        text, markup = await _render_schedule(cb, db)
    await safe_edit(cb, text, markup)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:day:"))
async def admin_toggle_day(cb: CallbackQuery):
    day = int(cb.data.split(":")[2])
    with session_scope() as db:
        days = set(get_setting(db, "working_days", []))
        days.symmetric_difference_update({day})
        set_setting(db, "working_days", sorted(days))
        text, markup = await _render_schedule(cb, db)
    await safe_edit(cb, text, markup)
    await cb.answer()


_SCHED_PROMPTS = {
    "start": (AdminSchedule.work_start, "🕘 Введіть час початку роботи у форматі HH:MM, напр. 09:00:"),
    "end": (AdminSchedule.work_end, "🕖 Введіть час завершення роботи у форматі HH:MM, напр. 19:00:"),
    "step": (AdminSchedule.slot_step, "⏱ Введіть крок слоту у хвилинах, напр. 60:"),
    "horizon": (AdminSchedule.horizon, "📆 На скільки днів вперед відкрити запис, напр. 31:"),
}


@router.callback_query(F.data.startswith("adm:sched:"))
async def admin_sched_edit(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":")[2]
    st, prompt = _SCHED_PROMPTS[key]
    await state.set_state(st)
    await safe_edit(cb, prompt)
    await cb.answer()


def _valid_hhmm(s: str) -> bool:
    try:
        h, m = s.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except (ValueError, AttributeError):
        return False


@router.message(AdminSchedule.work_start)
async def set_work_start(message: Message, state: FSMContext):
    if not _valid_hhmm(message.text.strip()):
        await message.answer("⚠️ Формат HH:MM, напр. 09:00")
        return
    with session_scope() as db:
        set_setting(db, "work_start", message.text.strip())
    await state.clear()
    await message.answer("✅ Збережено.", reply_markup=kb.admin_back_kb())


@router.message(AdminSchedule.work_end)
async def set_work_end(message: Message, state: FSMContext):
    if not _valid_hhmm(message.text.strip()):
        await message.answer("⚠️ Формат HH:MM, напр. 19:00")
        return
    with session_scope() as db:
        set_setting(db, "work_end", message.text.strip())
    await state.clear()
    await message.answer("✅ Збережено.", reply_markup=kb.admin_back_kb())


@router.message(AdminSchedule.slot_step)
async def set_slot_step(message: Message, state: FSMContext):
    if not message.text.strip().isdigit() or int(message.text.strip()) < 5:
        await message.answer("⚠️ Введіть число хвилин (мін. 5)")
        return
    with session_scope() as db:
        set_setting(db, "slot_step_min", int(message.text.strip()))
    await state.clear()
    await message.answer("✅ Збережено.", reply_markup=kb.admin_back_kb())


@router.message(AdminSchedule.horizon)
async def set_horizon(message: Message, state: FSMContext):
    if not message.text.strip().isdigit() or not (1 <= int(message.text.strip()) <= 120):
        await message.answer("⚠️ Введіть число від 1 до 120")
        return
    with session_scope() as db:
        set_setting(db, "horizon_days", int(message.text.strip()))
    await state.clear()
    await message.answer("✅ Збережено.", reply_markup=kb.admin_back_kb())


# ─────────────────────────── Клієнти ───────────────────────────
@router.callback_query(F.data.startswith("adm:clients:"))
async def admin_clients(cb: CallbackQuery):
    page = int(cb.data.split(":")[2])
    with session_scope() as db:
        q = db.query(User).filter(User.role == "user").order_by(User.created_at.desc())
        rows = q.offset(page * PAGE).limit(PAGE + 1).all()
        has_more = len(rows) > PAGE
        rows = rows[:PAGE]
        total = q.count()
        text = f"👥 <b>Клієнти</b> · всього {total}\nОберіть клієнта 👇" if rows else "👥 Клієнтів поки немає."
        markup = kb.clients_kb(rows, page, has_more)
    await safe_edit(cb, text, markup)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:client:"))
async def admin_client_detail(cb: CallbackQuery):
    cid = int(cb.data.split(":")[2])
    with session_scope() as db:
        u = db.get(User, cid)
        if not u:
            await cb.answer("Не знайдено", show_alert=True)
            return
        bookings = db.query(Booking).filter(Booking.user_id == cid).order_by(Booking.date.desc()).limit(8).all()
        hist = "\n".join(
            f"• {b.date} {b.time} — {STATUS_LABELS.get(b.status, b.status)}" for b in bookings
        ) or "записів немає"
        uname = f"@{u.username}" if u.username else "—"
        text = (
            f"👤 <b>{u.full_name}</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"🆔 Telegram: {uname} (<code>{u.telegram_id or '—'}</code>)\n"
            f"📱 Телефон: {u.phone or '—'}\n"
            f"🔔 Сповіщення: {'так' if u.notify else 'ні'}\n\n"
            f"<b>Останні записи:</b>\n{hist}"
        )
        markup = kb.client_detail_kb(cid)
    await safe_edit(cb, text, markup)
    await cb.answer()


# ─────────────────────────── Розсилка ───────────────────────────
@router.callback_query(F.data == "adm:bcast")
async def admin_broadcast(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminBroadcast.text)
    await safe_edit(cb, "📣 <b>Розсилка</b>\n\nНадішліть текст повідомлення, який отримають усі клієнти зі ввімкненими сповіщеннями:")
    await cb.answer()


@router.message(AdminBroadcast.text)
async def do_broadcast(message: Message, state: FSMContext):
    await state.clear()
    text = message.text
    sent = 0
    with session_scope() as db:
        recipients = db.query(User).filter(
            User.role == "user", User.telegram_id.isnot(None), User.notify == True  # noqa: E712
        ).all()
        ids = [u.telegram_id for u in recipients]
    for chat_id in ids:
        try:
            await message.bot.send_message(chat_id, f"📣 {text}")
            sent += 1
        except Exception:  # noqa: BLE001
            pass
    await message.answer(f"✅ Розсилку завершено. Доставлено: <b>{sent}/{len(ids)}</b>", reply_markup=kb.admin_back_kb())


# ─────────────────────────── Привітання ───────────────────────────
@router.callback_query(F.data == "adm:welcome")
async def admin_welcome(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminWelcome.text)
    with session_scope() as db:
        current = get_setting(db, "bot_welcome", "")
    await safe_edit(
        cb,
        f"💬 <b>Привітальне повідомлення</b>\n\nПоточне:\n<i>{current}</i>\n\nНадішліть новий текст "
        "(можна використати <code>{business}</code> для назви студії):",
    )
    await cb.answer()


@router.message(AdminWelcome.text)
async def save_welcome(message: Message, state: FSMContext):
    with session_scope() as db:
        set_setting(db, "bot_welcome", message.text)
    await state.clear()
    await message.answer("✅ Привітання оновлено.", reply_markup=kb.admin_back_kb())


# ─────────────────────────── Адміністратори ───────────────────────────
@router.callback_query(F.data == "adm:admins")
async def admin_admins(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    with session_scope() as db:
        info = list_admins(db)
    env_u = ", ".join("@" + u for u in info["env_usernames"]) or "—"
    env_i = ", ".join(str(i) for i in info["env_ids"]) or "—"
    text = (
        "👑 <b>Адміністратори</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"🔒 З .env (незмінні): {env_u}\n"
        f"🔒 ID з .env: {env_i}\n\n"
        "Нижче — адміни, додані в боті (їх можна видалити):"
    )
    await safe_edit(cb, text, kb.admins_kb(info["db_usernames"]))
    await cb.answer()


@router.callback_query(F.data == "adm:admin:add")
async def admin_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminAddAdmin.username)
    await safe_edit(cb, "➕ Надішліть username нового адміністратора (без @):")
    await cb.answer()


@router.message(AdminAddAdmin.username)
async def admin_add_save(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    with session_scope() as db:
        add_admin_username(db, username)
        existing = db.query(User).filter(User.username.ilike(username)).first()
        if existing:
            existing.role = "admin"
    await state.clear()
    await message.answer(f"✅ @{username} тепер адміністратор.", reply_markup=kb.admin_back_kb())


@router.callback_query(F.data.startswith("adm:admin:del:"))
async def admin_del(cb: CallbackQuery):
    username = cb.data.split(":", 3)[3]
    with session_scope() as db:
        remove_admin_username(db, username)
        existing = db.query(User).filter(User.username.ilike(username)).first()
        if existing:
            existing.role = "user"
        info = list_admins(db)
    await safe_edit(cb, "👑 <b>Адміністратори</b>\nСписок оновлено.", kb.admins_kb(info["db_usernames"]))
    await cb.answer("Видалено")
