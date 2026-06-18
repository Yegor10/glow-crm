# GlowCRM

**Telegram CRM-бот для запису на сеанси макіяжу**

GlowCRM — повноцінна CRM-система на [aiogram 3](https://docs.aiogram.dev), яка працює
**повністю всередині Telegram**. Клієнти записуються на сеанси в боті, а адміністратори
керують студією через вбудовану адмін-панель — без окремого сайту.

[:octicons-mark-github-16: Репозиторій](https://github.com/Yegor10/glow-crm){ .md-button }
[:octicons-rocket-16: Швидкий старт](#швидкий-старт){ .md-button .md-button--primary }

---

## Можливості

### Для клієнтів
- Запис на сеанс у 3 кроки: послуга → дата → час
- Перегляд і скасування власних записів
- Прайс послуг, налаштування телефону та сповіщень
- Автоматичні повідомлення про статус запису

### Для адміністраторів
- Замовлення з фільтрами за статусами та діями (підтвердити / виконати / скасувати)
- Статистика, дохід, графік завантаженості
- Керування послугами, графіком роботи, клієнтами
- Масові розсилки, редагування привітання
- Кілька адмінів за username або Telegram ID

---

## Швидкий старт

```bash
git clone https://github.com/Yegor10/glow-crm.git
cd glow-crm
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
# впишіть BOT_TOKEN та ADMIN_USERNAMES у .env
python run.py
```

У Telegram надішліть боту `/start`. Адміни побачать кнопку **Адмін-панель** або команду `/admin`.

!!! tip "Порада"
    Токен бота отримайте у [@BotFather](https://t.me/BotFather), а свій username впишіть
    у `ADMIN_USERNAMES`, щоб одразу отримати доступ до адмін-панелі.

---

## Технології

| Компонент | Технологія |
|-----------|------------|
| Telegram-бот | aiogram 3 |
| ORM | SQLAlchemy 2.0 |
| База даних | SQLite (WAL) |
| Конфігурація | python-dotenv |

---

## Розділи документації

| Документ | Опис |
|----------|------|
| [Архітектура](ARCHITECTURE.md) | Компоненти, модель даних, потоки |
| [Конфігурація](CONFIGURATION.md) | Змінні `.env`, адміни, графік |
| [Користувачам](USER_GUIDE.md) | Як записатися на сеанс |
| [Адміністраторам](ADMIN_GUIDE.md) | Панель керування в боті |
| [Розгортання](DEPLOYMENT.md) | systemd, Docker, оновлення |
