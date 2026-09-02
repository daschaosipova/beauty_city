# Салон красоты «Ольга Beauty» — Telegram-бот записи

Telegram-бот для записи клиентов в салон красоты. Написан на **aiogram 3** (бот) и **Django + SQLite** (данные и админка). Оплата, промокоды, отзывы и чаевые — реализованы как учебные/имитационные сценарии.

## Стек

| Компонент | Технология |
|---|---|
| Telegram-бот | Python 3.12+, aiogram 3 |
| Данные и админка | Django 6, SQLite |
| Конфигурация | `.env` (python-dotenv) |
| Часовой пояс | Europe/Moscow (UTC в БД, конвертация на выводе) |

## Возможности

- Запись через бота тремя сценариями:
  - «Выбрать салон» → процедура → мастер → дата/время
  - «К любимому мастеру» → процедура → салон → дата/время
  - «Мне нужна процедура» → дата → время → мастер → салон
- Показ цен и длительности процедур
- Согласие на обработку персональных данных (обязательно до записи)
- Имитация онлайн-оплаты: «Оплатить онлайн» (карта / СБП) или «Оплатить в салоне»; данные платежа сохраняются в записи
- Промокоды: «Применить промокод» на экране оплаты, скидка сразу пересчитывается; кнопка «Сбросить промокод»
- Отзывы: «Хочу оставить отзыв» — завершённые визиты без отзыва, оценка 1–5 и текст
- Чаевые: админ в разделе `/staff` создаёт одноразовую ссылку на оплату чаевых по завершённой записи; бот отправляет её клиенту в Telegram или даёт для копирования
- Запись по телефону через раздел сотрудника `/staff` (по паролю) — слоты блокируются транзакционно и не пересекаются с записями через бота
- Админка Django для управления салонами, услугами, мастерами, расписанием, записями, промокодами и отзывами

## Быстрый старт

Требуется **Python 3.12+**.

```bash
git clone <repo-url>
cd newversion

# виртуальное окружение
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# зависимости
pip install -r requirements.txt
```

### 1. Настройка `.env`

Создайте файл `.env` в корне проекта (шаблон — `.env.example`):

```ini
BOT_TOKEN=123456789:AA...
STAFF_PASSWORD=придумайте_пароль
DJANGO_SECRET_KEY=придумайте_секрет   # необязательно; по умолчанию dev-ключ
```

- `BOT_TOKEN` — токен бота из [@BotFather](https://t.me/BotFather)
- `STAFF_PASSWORD` — пароль для входа в раздел сотрудника (команда `/staff`)
- `DJANGO_SECRET_KEY` — необязательный секрет Django (если не задан, используется dev-ключ из `core/settings.py`)

> Все переменные окружения читаются в одном месте — `core/settings.py`.
> `.env` в `.gitignore` и в репозиторий не попадает. Не коммитьте реальные токены.

### 2. Миграции и данные

```bash
python manage.py migrate
python manage.py createsuperuser          # для админки
python manage.py populate_db              # тестовые данные
```

`populate_db` создаёт:
- 3 салона, 5 услуг, 3 мастера (связи мастер ↔ салоны/услуги)
- расписание на **сегодня + 4 дня вперёд** (каждый мастер чередует свои салоны по дням недели)
- 2 тестовых клиента, 1 завершённый визит (100 дней назад) и 1 активную запись
- промокоды `SALON10` (−10%) и `WELCOME500` (−15%)

Команда безопасна для перезапуска (`get_or_create`) — повторный запуск не создаёт дубликаты.

### 3. Запуск

```bash
python bot.py                # Telegram-бот
python manage.py runserver   # админка: http://127.0.0.1:8000/admin/
```

> Бот должен быть запущен **одним процессом**. Повторный запуск вызовет `TelegramConflictError`.
> После изменения кода перезапустите бот (Ctrl+C → `python bot.py` заново).

### Команды и сценарии в боте

| Команда | Что делает |
|---|---|
| `/start` | Главное меню записи |
| `/staff` | Раздел сотрудника (требует `STAFF_PASSWORD`): запись по телефону и чаевые |
| `/cancel` | Отмена текущего действия |

**Сценарий чаевых:** админ завершает визит в админке (статус `completed`) → `/staff` → «Чаевые» → выбирает запись → бот создаёт ссылку `https://t.me/<бот>?start=tip_<токен>` и отправляет её клиенту (или показывает для копирования). Клиент переходит по ссылке → выбирает сумму (кнопки или ручной ввод) → способ оплаты (карта/СБП) → сумма сохраняется в `tips_amount` записи.

## Структура проекта

```
project/
├── bot.py                     # точка входа: создаёт Bot/Dispatcher, регистрирует роутеры
├── manage.py
├── requirements.txt
├── .env.example               # шаблон переменных окружения
├── .gitignore
├── core/                      # настройки Django (settings, urls, wsgi/asgi)
├── bot_manager/
│   ├── models.py              # Salon, Service, Master, Client, TimeSlot, PromoCode, Appointment, Review
│   ├── admin.py               # админки всех моделей
│   ├── migrations/            # миграции БД (0001–0005)
│   └── management/commands/populate_db.py
└── salon_bot/
    ├── handlers.py            # /start (в т.ч. deep-link чаевых), /cancel, меню
    ├── salon_handlers.py      # сценарий «Выбрать салон»
    ├── master_handlers.py     # сценарий «К любимому мастеру»
    ├── procedure_handlers.py  # сценарий «Мне нужна процедура»
    ├── phone_handlers.py      # сценарий «Хочу записаться по телефону»
    ├── shared_handlers.py     # согласие на ПД, телефон, подтверждение записи
    ├── payment_handlers.py    # онлайн-оплата, промокоды
    ├── review_handlers.py     # отзывы
    ├── staff_handlers.py      # раздел сотрудника (/staff), ссылки на чаевые
    ├── tip_handlers.py        # оплата чаевых по deep-link
    ├── keyboards.py           # все инлайн/reply-клавиатуры
    ├── services.py            # работа с БД (async-обёртки над ORM)
    ├── states.py              # FSM-состояния всех сценариев
```

## Как устроен код (для разработчиков)

### Архитектура

- **Один роутер на сценарий.** Каждый `*_handlers.py` регистрирует свой `Router`, который подключается в `bot.py`. Хендлеры внутри роутера не конфликтуют между сценариями.
- **FSM-состояния** вынесены в `states.py` (`BookingStates`, `MasterFirstStates`, `ProcedureFirstStates`, `StaffStates`, `PromoStates`, `ReviewStates`, `TipStates`). Переходы между шагами — через `state.set_state()` + `StateFilter`.
- **Клавиатуры** — чистые функции в `keyboards.py`, возвращающие `InlineKeyboardMarkup` / `ReplyKeyboardMarkup`. Callback-данные имеют префикс сценария: `salon:`, `master:`, `st:` (staff), `pay:`, `review:`, `tip:`.
- **Вся работа с БД — в `services.py`** через `sync_to_async`. Хендлеры никогда не трогают ORM напрямую.

### Важные правила

1. **Django ORM нельзя читать из async-контекста.** Обращение к `ForeignKey`-полям (например, `appointment.slot.master`) вне `sync_to_async` вызывает `SynchronousOnlyOperation`. Все чтения БД и FK — внутри `sync_to_async(lambda: ...)()` или через `@sync_to_async` функции в `services.py`.
2. **Запись слота транзакционна.** `create_appointment` использует `select_for_update` + флаг `is_booked` в одной транзакции — двойная запись исключена даже при конкурентном бронировании.
3. **`edit_text` с тем же текстом → ошибка Telegram.** Игнорируется через `_safe_edit` (см. `payment_handlers.py` / `staff_handlers.py`) и через router-level обработчик ошибок `@staff_router.errors.register`.
4. **Повторные запуски бота запрещены** (`TelegramConflictError`).

### Как добавить новую фичу

1. `states.py` — опционально новое `StatesGroup`.
2. `services.py` — функции работы с БД через `sync_to_async`.
3. `keyboards.py` — клавиатуры и callback-префиксы.
4. Новый `*_handlers.py` с `Router` + подключить в `bot.py`.
5. `bot_manager/models.py` + миграция (`python manage.py makemigrations && python manage.py migrate`) — при изменении модели.
6. Проверить `python manage.py check` и перезапустить бот.

## Модели данных

| Модель | Назначение | Ключевые поля |
|---|---|---|
| `Salon` | Филиал салона | name, address, phone |
| `Service` | Услуга | name, price, duration_minutes |
| `Master` | Мастер | full_name, salons (M2M), services (M2M), is_active |
| `Client` | Клиент | telegram_id, username, phone, is_terms_accepted |
| `TimeSlot` | Свободное окно | master, salon, date, time, is_booked |
| `PromoCode` | Промокод | code, discount_percent, is_active, valid_until |
| `Appointment` | Запись | client, slot (OneToOne), service, status, оплата (`paid_at`, `payment_method`, `payment_id`), промокод (`discount_amount`, `final_price`), чаевые (`tips_amount`, `tips_token`, `tips_paid_at`…) |
| `Review` | Отзыв | client, master, appointment (unique), rating 1–5, text |

Статусы записи: `pending` (ожидает оплаты), `paid` (оплачено), `completed` (визит завершён), `cancelled`.

## Тестирование

Автоматических тестов пока нет (`bot_manager/tests.py` пуст). Проверки выполняются вручную:

- `python manage.py check` — проверка конфигурации Django
- `python manage.py shell` — сквозная проверка сервисов (например, `pay_tips`, `apply_promo_code`)
- Прогон сценария в боте после перезапуска

## Безопасность

- Секреты — только в `.env`, файл в `.gitignore`
- `/staff` защищён паролем (`hmac.compare_digest`)
- Запись блокирует слот транзакционно — нет двойного бронирования
- Ссылка на чаевые одноразовая и привязана к записи (у клиента с известным `telegram_id` — только его ссылка)

## Ограничения (учебный проект)

- Оплата имитационная: реальные платёжные провайдеры не подключены
- `DEBUG = True`, `ALLOWED_HOSTS = []` — только для локальной разработки
- Телефоны/данные тестовых клиентов — фиктивные
