# Розгортання GlowCRM

Бот працює через **long polling**, тому не потребує відкритих портів, домену чи HTTPS —
достатньо доступу до інтернету. Нижче — кілька способів запуску.

## Зміст
- [Локальний запуск](#локальний-запуск)
- [Linux + systemd](#linux--systemd)
- [Docker](#docker)
- [Docker Compose](#docker-compose)
- [Оновлення](#оновлення)
- [Резервне копіювання](#резервне-копіювання)
- [Поширені проблеми](#поширені-проблеми)

---

## Локальний запуск

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # Windows: copy .env.example .env
# заповніть BOT_TOKEN та ADMIN_USERNAMES
python run.py
```

---

## Linux + systemd

Для постійної роботи на сервері створіть службу.

`/etc/systemd/system/glowcrm.service`:

```ini
[Unit]
Description=GlowCRM Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/glow-crm
ExecStart=/opt/glow-crm/.venv/bin/python run.py
Restart=always
RestartSec=5
User=glowcrm
EnvironmentFile=/opt/glow-crm/.env

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now glowcrm
sudo systemctl status glowcrm
journalctl -u glowcrm -f          # перегляд логів
```

---

## Docker

```bash
docker build -t glow-crm .
docker run -d --name glow-crm \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  --restart unless-stopped \
  glow-crm
```

Том `data/` зберігає базу між перезапусками.

---

## Docker Compose

```bash
docker compose up -d --build
docker compose logs -f
docker compose down
```

`docker-compose.yml` уже налаштований: читає `.env`, монтує `./data` і перезапускається автоматично.

---

## Оновлення

```bash
git pull
# локально:
pip install -r requirements.txt
sudo systemctl restart glowcrm
# або Docker:
docker compose up -d --build
```

База даних сумісна між запусками; нові налаштування/послуги додаються при ініціалізації,
не перезаписуючи наявні.

---

## Резервне копіювання

Уся інформація — у `data/glowcrm.sqlite3`. Достатньо копіювати цей файл (краще при зупиненому боті):

```bash
cp data/glowcrm.sqlite3 backups/glowcrm-$(date +%F).sqlite3
```

---

## Поширені проблеми

**`Не вказано BOT_TOKEN`.**
Не створено `.env` або порожня змінна `BOT_TOKEN`. Скопіюйте `.env.example` і впишіть токен.

**Не бачу кнопку «Адмін-панель».**
Ваш `username`/ID не в списку адмінів. Перевірте `ADMIN_USERNAMES` / `ADMIN_IDS` та
перезапустіть бота. Username вказується без `@`.

**`TelegramConflictError: terminated by other getUpdates`.**
Запущено два екземпляри бота з тим самим токеном. Залиште лише один.

**Кирилиця/емодзі «ламаються» в консолі Windows.**
Застосунок сам перемикає вивід на UTF-8; за потреби виконайте `chcp 65001` перед запуском.
