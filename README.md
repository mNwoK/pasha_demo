# Shop API — минимальный пример бекенда на FastAPI

Учебный проект: интернет-магазин с пользователями, товарами и корзинами.
Показывает базовый набор инструментов бекенд-разработки на Python.

📖 **[GUIDE.md](GUIDE.md) — подробное учебное руководство**: как проект сделан,
зачем нужен каждый инструмент, схема базы данных и жизненный цикл запроса.

## Стек и зачем он нужен

| Инструмент | Роль |
| --- | --- |
| **FastAPI** | веб-фреймворк: роуты, валидация, автоматическая документация (Swagger на `/docs`) |
| **uv** | менеджмент окружения и зависимостей (быстрая замена pip + virtualenv) |
| **PostgreSQL + asyncpg** | база данных и асинхронный драйвер; SQL пишем руками |
| **Alembic** | миграции схемы БД |
| **Pydantic** | схемы данных (валидация запросов/ответов), настройки |
| **pytest + httpx** | тесты: httpx позволяет дёргать приложение без реального сервера |
| **Docker / Compose** | единообразный запуск приложения и базы |

## Структура проекта

```
.
├── app/
│   ├── main.py            # точка входа: создаёт FastAPI, lifespan (пул соединений)
│   ├── config.py          # настройки из env / .env
│   ├── database.py        # пул asyncpg + FastAPI-зависимость get_pool
│   ├── schemas.py         # Pydantic-схемы: что принимаем и что отдаём
│   └── routers/           # по роутеру на сущность
│       ├── users.py
│       ├── products.py
│       └── cart.py
├── alembic/               # миграции БД
│   ├── env.py             # подключает Alembic к БД (URL из DATABASE_URL)
│   └── versions/0001_init.py
├── tests/                 # pytest-тесты
├── pyproject.toml         # зависимости проекта + настройки pytest
├── Dockerfile
└── docker-compose.yml     # postgres + api
```

## Первый запуск: от клона до проверенных эндпоинтов

Требуется: **Docker с Compose** и свободный порт **5432** (если запущен локальный Postgres — остановите его или поменяйте порт в `docker-compose.yml`). Python и uv не нужны — всё работает в контейнерах.

```bash
# 1. Заходим в склонированный проект
cd [ИМЯ_ПАПКИ]          # имя папки вашего репозитория

# 2. Поднимаем БД и API целиком — миграции применятся автоматически
docker compose up -d --build

# 3. Проверяем, что сервис жив
curl http://localhost:8000/healthz
# {"status":"ok"}
```
После запуска:

- API: http://localhost:8000
- Swagger UI (можно дёргать эндпоинты из браузера): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- База: localhost:5432 (postgres/postgres)

Остановка:

```bash
docker compose down      # остановить (данные сохранятся в томе pgdata)
docker compose down -v   # остановить и удалить данные БД — следующий запуск с чистой базы
```

Замечания:

- Зависимости подтягиваются автоматически: при сборке Docker скачает
  базовые образы (`python:3.13-slim`, `postgres:16-alpine`, образ `uv`)
  и внутри образа установит все Python-зависимости (`uv sync` в Dockerfile).
  Нужен только интернет при первом запуске — дальше всё кэшируется.
- Файл `.env` для этого способа **не нужен** — Compose сам передаёт `DATABASE_URL` в контейнер, а `.env` не попадает в образ (см. `.dockerignore`). Он понадобится для локального запуска через `uv` и для тестов.
- Миграции применяются перед стартом сервера (`CMD` в Dockerfile), поэтому сразу после `up` таблицы уже готовы.

## Локальный запуск через uv

```bash
uv sync                # создаёт .venv и ставит зависимости (включая dev)
cp .env.example .env   # настройки читаются из .env

# нужна работающая PostgreSQL, например:
docker compose up -d db

uv run alembic upgrade head     # применить миграции
uv run uvicorn app.main:app --reload   # запустить сервер
```

## Миграции (Alembic)

```bash
uv run alembic revision -m "add orders table"   # создать заготовку
uv run alembic upgrade head                       # применить все миграции
uv run alembic downgrade -1                       # откатить последнюю
uv run alembic history                            # посмотреть цепочку
```

В этом проекте нет моделей SQLAlchemy — миграции пишутся руками через
`op.execute(...)` в `alembic/versions/` (доступ к БД идёт через asyncpg).

## Тесты

```bash
docker compose up -d db        # тесты тоже нуждаются в PostgreSQL
uv run pytest -v
```

Тестовая база (`shop_test`) создаётся автоматически, миграции применяются
перед запуском, таблицы очищаются перед каждым тестом. Для другой базы —
переменная `TEST_DATABASE_URL`.

## API

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/healthz` | проверка работоспособности |
| POST | `/users` | создать пользователя |
| GET | `/users` | список пользователей (`?limit=&offset=`) |
| GET | `/users/{id}` | получить пользователя |
| POST | `/products` | создать товар |
| GET | `/products` | список товаров |
| GET | `/products/{id}` | получить товар |
| POST | `/cart/{user_id}/items` | добавить товар в корзину (`{product_id, quantity}`) |
| GET | `/cart/{user_id}` | получить корзину с итогом |
| PUT | `/cart/{user_id}/items/{product_id}` | изменить количество |
| DELETE | `/cart/{user_id}/items/{product_id}` | удалить товар из корзины |

## Как это устроено

1. **Запуск.** `uvicorn app.main:app` вызывает фабрику `create_app()` из
   `app/main.py`. При старте срабатывает `lifespan`: открывается пул
   соединений asyncpg и кладётся в `app.state.pool`. При остановке пул закрывается.
2. **Запрос.** FastAPI находит роутер (`app/routers/*.py`), валидирует тело
   запроса через Pydantic-схему (`app/schemas.py`).
3. **БД.** Роутер получает пул через зависимость `Depends(get_pool)` и выполняет
   SQL-параметризованные запросы (`$1, $2...`) через asyncpg.
4. **Ответ.** Строки из БД (`asyncpg.Record`) конвертируются в Pydantic-схемы
   `model_validate(...)`, FastAPI сериализует их в JSON.
5. **Схема БД.** Управляется миграциями Alembic, а не кодом приложения.
6. **Документация.** Swagger (`/docs`) генерируется автоматически из Pydantic-схем
   и описаний эндпоинтов (`summary=...`, `tags=...`).

## Полезные команды

```bash
uv run python -c "import app"          # проверить, что приложение импортируется
uv run alembic upgrade head            # миграции
uv run pytest                          # тесты
docker compose logs -f api             # логи
docker compose down -v                 # остановить и удалить тома
```
