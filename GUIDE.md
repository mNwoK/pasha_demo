# Как сделан этот проект — учебное руководство

Пошаговый разбор мини-бекенда интернет-магазина на FastAPI.
Пишется «для новичка»: каждый инструмент объяснён своими словами.

---

## 1. Что мы строим

HTTP API интернет-магазина с тремя сущностями:

- **Пользователи** — кто покупает
- **Товары** — что продаётся
- **Корзина** — связь «пользователь ↔ товар» с количеством

Примеры запросов:

```
POST /users                     создать пользователя
GET  /users/1                   получить пользователя
POST /products                  создать товар
GET  /products                  список товаров
POST /cart/1/items              положить товар в корзину пользователя №1
GET  /cart/1                    посмотреть корзину с итоговой суммой
PUT  /cart/1/items/2            изменить количество
DELETE /cart/1/items/2          убрать товар из корзины
```

---

## 2. Какие инструменты и зачем

| Инструмент | Что делает | Зачем здесь |
| --- | --- | --- |
| **Python 3.13** | язык | всё пишем на нём |
| **FastAPI** | веб-фреймворк | роуты, валидация, автоматический Swagger |
| **uv** | менеджер окружения | быстрая замена `pip` + `virtualenv`: создаёт `.venv` и ставит зависимости одной командой |
| **PostgreSQL** | реляционная БД | надёжное хранилище данных |
| **asyncpg** | драйвер PostgreSQL | асинхронное общение с БД; SQL пишем руками |
| **Alembic** | миграции | версионирование схемы БД (таблиц и колонок) |
| **Pydantic** | валидация данных | проверяет входящий JSON и формирует исходящий |
| **pydantic-settings** | настройки | читает конфиг из переменных окружения и `.env` |
| **pytest** | тесты | автопроверка, что код работает |
| **pytest-asyncio** | асинхронные тесты | позволяет писать тесты с `async def` |
| **httpx** | HTTP-клиент | в тестах дёргает наше API без реального сервера |
| **Docker / Compose** | контейнеры | одинаковый запуск у всех: база + приложение |

---

## 3. Структура файлов

```
.
├── pyproject.toml          # «паспорт» проекта: зависимости и настройки
├── uv.lock                 # зафиксированные версии зависимостей
├── Dockerfile              # как собрать образ приложения
├── docker-compose.yml      # два сервиса: БД и API
├── alembic.ini             # настройки Alembic
├── alembic/
│   ├── env.py              # как Alembic подключается к БД
│   └── versions/0001_init.py   # первая миграция: создаёт таблицы
├── app/
│   ├── main.py             # точка входа: создаёт FastAPI
│   ├── config.py           # настройки (URL базы и т.д.)
│   ├── database.py         # пул соединений к БД
│   ├── schemas.py          # Pydantic-схемы запросов/ответов
│   └── routers/            # по файлу на группу эндпоинтов
│       ├── users.py
│       ├── products.py
│       └── cart.py
└── tests/                  # pytest-тесты  
    ├── conftest.py         
    ├── test_users.py
    ├── test_products.py
    └── test_cart.py
```

---

## 4. Пошагово: как это создавалось

### Шаг 1. Проект и окружение (uv)

`pyproject.toml` — центральный файл. В нём:

```toml
[project]
name = "shop-example"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",      # сервер, который запускает приложение
    "pydantic[email]>=2.5",         # валидация + EmailStr
    "pydantic-settings>=2.5",       # настройки из .env
    "python-dotenv>=1.0",           # чтение .env (нужно Alembic)
    "asyncpg>=0.30",                # драйвер PostgreSQL
    "alembic>=1.14",                # миграции
    "sqlalchemy[asyncio]>=2.0.36",  # нужна Alembic (даже без моделей!)
    "httpx>=0.27",                  # тестовый HTTP-клиент
]

[dependency-groups]
dev = ["pytest>=8.3", "pytest-asyncio>=0.25"]   # только для разработки
```

Команды:

```bash
uv sync        # создал .venv и поставил всё из pyproject.toml (+ uv.lock)
uv run pytest  # запускает команду внутри виртуального окружения
```

`uv.lock` — «замороженные» версии всех зависимостей (включая транзитивные).
Он даёт воспроизводимость: у всех одинаковый набор пакетов.

---

### Шаг 2. Настройки (`app/config.py`)

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/shop"
```

- Значения читаются из **переменных окружения** и файла **`.env`**
- `extra="ignore"` — чужие переменные (например, `TEST_DATABASE_URL`) не ломают настройки
- `@lru_cache` на `get_settings()` — настройки читаются один раз

Файл `.env` (не коммитится в git, см. `.gitignore`):

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/shop
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/shop_test
```

---

### Шаг 3. База данных (`app/database.py`)

**Что такое пул соединений?** Открывать TCP-соединение к Postgres на каждый запрос — дорого.
Поэтому при старте приложения создаётся пул (горстка уже открытых соединений),
и запросы берут соединения из него.

```python
async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=_asyncpg_dsn(), min_size=1, max_size=10)
```

Мелочь, о которой легко забыть: SQLAlchemy/Alembic используют URL
`postgresql+asyncpg://...`, а asyncpg — `postgresql://...`, поэтому суффикс убирается.

`get_pool` — это **FastAPI-зависимость** (`Depends(get_pool)`): роутер не знает,
где пул хранится, он просто просит его «по имени».

---

### Шаг 4. Схемы данных (`app/schemas.py`)

Pydantic-схемы — это «договор» API. Делим на две группы:

- `UserCreate` / `ProductCreate` / `CartItemAdd` — что клиент **присылает**
  (тут валидация: `price > 0`, `email` похож на email, `stock >= 0`)
- `UserRead` / `ProductRead` / `CartRead` — что API **отвечает**

Пример:

```python
class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    price: Decimal = Field(gt=0)      # больше нуля, точная дробь (не float!)
    stock: int = Field(ge=0, default=0)
```

Почему `Decimal`, а не `float`? Для денег float даёт ошибки округления
(`0.1 + 0.2 != 0.3`). `Decimal` хранит точное значение.

Если прислать `{"price": -5}`, FastAPI сам ответит **422 Unprocessable Entity**
с объяснением — без единой строки кода проверки в роутере.

---

### Шаг 5. Роутеры (`app/routers/`)

Каждый роутер — набор эндпоинтов одной сущности. Пример создания пользователя:

```python
@router.post("", response_model=UserRead, status_code=201)
async def create_user(payload: UserCreate, pool: Pool = Depends(get_pool)):
    try:
        row = await pool.fetchrow(
            "INSERT INTO users (username, email) VALUES ($1, $2) "
            "RETURNING id, username, email, created_at",
            payload.username, payload.email,
        )
    except UniqueViolationError:
        raise HTTPException(status_code=409, detail="...")
    return UserRead.model_validate(dict(row))
```

Разберём по деталям:

- `$1, $2` — **параметризованный запрос**: значения подставляются отдельно от SQL,
  поэтому SQL-инъекции невозможны (никогда не склеивайте строки!)
- `RETURNING` — PostgreSQL сразу возвращает вставленную строку
- `UniqueViolationError` — asyncpg кидает при нарушении `UNIQUE` → отвечаем 409
- `asyncpg.Record` — строка из БД. **Не поддерживает** `record.id` (только `record["id"]`),
  поэтому конвертируем через `dict(row)` перед Pydantic
- `response_model=UserRead` — FastAPI сам проверит и отфильтрует ответ по схеме

Особенность корзины: строка «пользователь + товар» уникальна, поэтому повторное
добавление не дублирует, а увеличивает количество — через `ON CONFLICT ... DO UPDATE`:

```sql
INSERT INTO cart_items (user_id, product_id, quantity) VALUES ($1, $2, $3)
ON CONFLICT (user_id, product_id)
DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
```

Это называется **upsert** («вставь или обнови»).

---

### Шаг 6. Точка входа (`app/main.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()   # старт: открыли пул
    yield
    await app.state.pool.close()           # останов: закрыли пул
```

**Lifespan** — современный способ запускать код при старте/остановке приложения
(заменяет устаревший `@app.on_event`). Пул храним в `app.state` — общем «кармане» приложения.

Дальше — фабрика:

```python
def create_app() -> FastAPI:
    app = FastAPI(title="Shop API", description="...", version="0.1.0")
    app.include_router(users.router, prefix="/users", tags=["Пользователи"])
    ...
```

Почему фабрика `create_app()`, а не просто `app = FastAPI()`? Так тестам и
разным конфигурациям проще создавать свои экземпляры.

**Swagger**: FastAPI сам генерирует документацию. Достаточно зайти на:

- `/docs` — Swagger UI (интерактивная, можно дёргать эндпоинты прямо из браузера)
- `/redoc` — ReDoc (более «документальный» вид)
- `/openapi.json` — схема, из которой строятся оба

Документация берётся из: Pydantic-схем, `summary=`, `tags=`, `description=`.

---

### Шаг 7. Миграции (Alembic)

**Зачем миграции?** Схема БД меняется со временем. Миграции — это «история изменений»:
каждое изменение — файл, который умеет `upgrade()` (применить) и `downgrade()` (откатить).

`alembic.ini` — где искать папку с миграциями (`script_location = alembic`).
`alembic/env.py` — подключается к БД; URL берёт из `DATABASE_URL`
(через `load_dotenv()`, потому что Alembic сам не читает `.env`).

Первая миграция (`alembic/versions/0001_init.py`) — **написана руками** через
`op.execute(SQL)`. Обычно миграции генерируются из моделей SQLAlchemy (`--autogenerate`),
но здесь мы работаем через asyncpg без моделей — поэтому raw SQL.

```bash
uv run alembic upgrade head      # применить все миграции
uv run alembic revision -m "..." # создать заготовку новой
uv run alembic downgrade -1      # откатить последнюю
uv run alembic history           # цепочка миграций
```

В контейнере миграции применяются автоматически перед запуском сервера
(смотрите `CMD` в Dockerfile).

#### Полная картина: как создаётся база данных

«База данных» в этом проекте появляется в три слоя:

**Слой 1. Сервер PostgreSQL и сама база `shop`** — `docker-compose.yml`.

Образ `postgres:16-alpine` при **первом** запуске читает переменные
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` и сам создаёт
пользователя и базу `shop` (это поведение официального образа).
Данные лежат в томе `pgdata`, поэтому `docker compose down`
(без `-v`) базу не удаляет, а `down -v` — удаляет.

```bash
docker compose up -d db   # Postgres поднялся, база shop существует, но таблиц в ней ещё нет
```

Готовность проверяет `healthcheck` (`pg_isready -U postgres -d shop`) —
именно поэтому `api` ждёт `condition: service_healthy`.

Локально, без Docker, базу нужно создать самому:

```bash
createdb -U postgres shop          # или: psql -c "CREATE DATABASE shop;"
```

**Слой 2. Схема (таблицы) — миграция Alembic.**

Таблицы `users`, `products`, `cart_items` создаёт миграция
`alembic/versions/0001_init.py`: руками написанный SQL внутри
`op.execute(...)`. Применяется одной командой:

```bash
uv run alembic upgrade head
```

Как Alembic подключается (`alembic/env.py`):

1. `load_dotenv()` — подтягивает `DATABASE_URL` из `.env`
   (Alembic сам `.env` не читает);
2. URL из окружения ставится в конфиг (`sqlalchemy.url`);
3. асинхронный движок SQLAlchemy (`NullPool`) прогоняет миграции
   внутри транзакции — при ошибке вся партия откатывается.

В Docker всё это делает `CMD` контейнера перед стартом сервера:
`alembic upgrade head && uvicorn ...` — поэтому сразу после
`docker compose up --build` схема уже готова.

**Слой 3. Тестовая база `shop_test`** — `tests/conftest.py`.

Фикстура `prepare_test_db` (один раз на всю сессию pytest):

1. подключается к служебной базе `postgres` — команда `CREATE DATABASE`
   не может выполняться внутри транзакции, поэтому соединение идёт
   не в целевую БД, а в «обслуживающую»;
2. сверяет `pg_database` и создаёт `shop_test`, только если её нет;
3. подставляет `DATABASE_URL=TEST_DATABASE_URL` и запускает
   `python -m alembic upgrade head` как подпроцесс — те же самые
   миграции применяются к тестовой БД (тестируем реальную схему,
   а не мок).

Итог: в одном Postgres живут две базы (`shop` и `shop_test`) с
одинаковой схемой; руками ничего создавать не нужно —
Compose создаёт сервер, Alembic — таблицы, pytest — свою базу.

---

### Шаг 8. Docker

**`docker-compose.yml`** — два сервиса:

```yaml
services:
  db:                    # PostgreSQL 16
    image: postgres:16-alpine
    environment: { POSTGRES_USER: postgres, POSTGRES_PASSWORD: postgres, POSTGRES_DB: shop }
    volumes: [pgdata:/var/lib/postgresql/data]   # чтобы данные не пропали
    healthcheck: ...                             # "pg_isready" — готов ли принимать
  api:
    build: .             # собирает Dockerfile
    environment: { DATABASE_URL: postgresql+asyncpg://...@db:5432/shop }
    depends_on: { db: { condition: service_healthy } }   # ждать готовности БД
```

Внутри сети Compose контейнеры обращаются друг к другу **по имени сервиса**
(`db`, а не `localhost`).

**`Dockerfile`**:

```dockerfile
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/   # ставим uv в образ
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"     # чтобы alembic/uvicorn были в PATH
COPY pyproject.toml uv.lock ./      # сначала только манифесты — кэш слоя
RUN uv sync --frozen --no-dev --no-install-project   # ставим зависимости
COPY . .                            # потом код
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

Ключевая идея Docker: **слои кэшируются**. Пока не менялись `pyproject.toml`
и `uv.lock`, слой с зависимостями переиспользуется — пересборка быстрая.

Запуск:

```bash
docker compose up --build
```

---

### Шаг 9. Тесты (pytest)

Тесты живут в `tests/`, общие «фундаменты» — в `conftest.py`:

1. **Один раз на сессию**: создаётся отдельная БД `shop_test` и к ней
   применяются те же миграции Alembic (так тестируется реальная схема).
2. **На каждый тест**: пул asyncpg, очистка таблиц (`TRUNCATE ... CASCADE`),
   HTTP-клиент httpx, который дёргает приложение **внутри процесса**
   (`ASGITransport`) — без сети и без реального сервера.

```python
@pytest_asyncio.fixture
async def client(pool):
    app.state.pool = pool            # lifespan не запускается — подставляем пул сами
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

`asyncio_mode = "auto"` в pyproject.toml → тесты с `async def` запускаются
без декоратора `@pytest.mark.asyncio`.

Пример теста:

```python
async def test_create_user(client):
    response = await client.post("/users", json={"username": "ivan", "email": "ivan@example.com"})
    assert response.status_code == 201
    assert response.json()["username"] == "ivan"
```

Запуск:

```bash
uv run pytest -v      # 18 тестов: пользователи, товары, корзина, ошибки (404/409/400/422)
```

---

## 5. Схема базы данных

Три таблицы в PostgreSQL:

```
┌──────────────┐        ┌───────────────────┐        ┌──────────────┐
│    users     │        │    cart_items     │        │   products   │
├──────────────┤        ├───────────────────┤        ├──────────────┤
│ id  BIGSERIAL│◄──┐    │ user_id  BIGINT   │    ┌──►│ id BIGSERIAL │
│ username     │   └────│ product_id BIGINT │────┘   │ name         │
│ email        │ PK(comp)│ quantity INT     │        │ description  │
│ created_at   │        │        PK (user_id,│        │ price        │
└──────────────┘        │         product_id)│        │ stock        │
  UNIQUE username       └───────────────────┘        └──────────────┘
  UNIQUE email
```

### Таблица `users`

| Колонка | Тип | Ограничения | Что означает |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL` | PRIMARY KEY | автоинкрементный номер (8 байт) |
| `username` | `VARCHAR(100)` | NOT NULL, UNIQUE | логин, уникальный |
| `email` | `VARCHAR(255)` | NOT NULL, UNIQUE | почта, уникальная |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | время создания с часовым поясом |

### Таблица `products`

| Колонка | Тип | Ограничения | Что означает |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL` | PRIMARY KEY | номер товара |
| `name` | `VARCHAR(200)` | NOT NULL | название |
| `description` | `TEXT` | nullable | описание (может быть пустым) |
| `price` | `NUMERIC(10,2)` | CHECK (price > 0) | цена: всего 10 цифр, 2 после запятой |
| `stock` | `INTEGER` | DEFAULT 0, CHECK (stock >= 0) | сколько на складе |

### Таблица `cart_items` (связь «многие-ко-многим» с количеством)

| Колонка | Тип | Ограничения | Что означает |
| --- | --- | --- | --- |
| `user_id` | `BIGINT` | FK → users(id), ON DELETE CASCADE | чей товар |
| `product_id` | `BIGINT` | FK → products(id), ON DELETE CASCADE | какой товар |
| `quantity` | `INTEGER` | CHECK (quantity > 0) | сколько штук |
| PRIMARY KEY | `(user_id, product_id)` | составной | одного товара в корзине — одна строка |

### Почему именно так

- **`BIGSERIAL`** вместо `SERIAL` — 8-байтные id на всякий случай (много данных).
- **`NUMERIC`** вместо `FLOAT` для цены — точные деньги без ошибок округления.
- **`TIMESTAMPTZ`** — время всегда с часовым поясом, чтобы не путаться.
- **`CHECK`** — БД сама не даст вставить отрицательную цену или количество.
- **`ON DELETE CASCADE`** — если удалить пользователя, его корзина удалится
  автоматически (для товаров — наоборот: удаление товара убирает его из всех корзин).
- **Составной PK** `(user_id, product_id)` — физически не позволяет держать
  две строки «пользователь + товар», поэтому добавление работает через upsert.
- Связь «корзина → товары» — это паттерн **junction table** (таблица-связь):
  один пользователь — много товаров, один товар — во многих корзинах.

### Типичный запрос с JOIN

Содержимое корзины собирается JOIN-ом трёх таблиц:

```sql
SELECT ci.product_id, p.name, p.price, ci.quantity,
       (p.price * ci.quantity) AS total
FROM cart_items ci
JOIN products p ON p.id = ci.product_id
WHERE ci.user_id = $1;
```

---

## 6. Жизненный цикл одного запроса

Возьмём `POST /cart/1/items` с телом `{"product_id": 1, "quantity": 2}`:

1. **uvicorn** принимает HTTP-запрос и передаёт его в FastAPI.
2. FastAPI находит роут `add_to_cart` в `app/routers/cart.py`.
3. Тело запроса валидируется Pydantic-схемой `CartItemAdd`
   (не число/`quantity <= 0` → сразу 422).
4. Срабатывает зависимость `Depends(get_pool)` — роутер получает пул из `app.state`.
5. Проверяется существование пользователя и товара (`SELECT ... WHERE id = $1`).
6. Проверяется `quantity <= stock` (иначе 400).
7. `INSERT ... ON CONFLICT DO UPDATE` — upsert строки корзины.
8. `SELECT ... JOIN` — читаем позицию с итогом, конвертируем `dict(row)` → `CartItemRead`.
9. FastAPI сериализует ответ в JSON: `{"product_id":1,"name":"Мышь","price":"100.00","quantity":2,"total":"200.00"}`.

Все обращения к БД — **асинхронные** (`await`), поэтому один процесс
обслуживает много запросов параллельно, не блокируясь на БД.

---

## 7. Как запускать

```bash
# всё целиком (БД + API), миграции применятся сами:
cp .env.example .env
docker compose up --build

# локально через uv (нужен запущенный Postgres):
uv sync
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# тесты (нужен Postgres, тестовая БД создастся сама):
uv run pytest -v
```

Проверка: http://localhost:8000/docs — Swagger, http://localhost:8000/healthz — статус.

---

## 8. Грабли, на которые мы наступили (полезно знать)

1. **`alembic: script_location not found`** — в `alembic.ini` обязательно
   `script_location = alembic`.
2. **`greenlet` / `No module named`** — async-SQLAlchemy требует extra
   `sqlalchemy[asyncio]`.
3. **`EmailStr`** требует extra `pydantic[email]`.
4. **`asyncpg.Record`** не поддерживает доступ по атрибуту (`row.id`) —
   только `row["id"]`; перед Pydantic делаем `dict(row)`.
5. **Alembic не читает `.env` сам** — нужен `load_dotenv()` в `env.py`.
6. **pydantic-settings по умолчанию запрещает лишние env-переменные**
   (`TEST_DATABASE_URL` ломал настройки) → `extra="ignore"`.
7. **В Docker `.venv/bin` не в PATH** → `ENV PATH="/app/.venv/bin:$PATH"`,
   иначе `alembic: not found`.
8. **`docker-credential-desktop: not found`** — помощник Docker Desktop не в PATH
   терминала; лечится добавлением `/Applications/Docker.app/Contents/Resources/bin` в PATH.
9. **pytest не находит пакет `app`** → `pythonpath = ["."]` в `[tool.pytest.ini_options]`.

---

## 9. Словарик

- **Эндпоинт (endpoint)** — URL + метод, «точка» API.
- **Роутер (router)** — группа эндпоинтов.
- **Схема (schema)** — описание формы данных (поля, типы, ограничения).
- **Миграция (migration)** — файл-изменение схемы БД с возможностью отката.
- **Пул соединений (connection pool)** — переиспользуемые соединения с БД.
- **Lifespan** — код при старте/остановке приложения.
- **Upsert** — «вставить или обновить» (`ON CONFLICT DO UPDATE`).
- **Fixture (фикстура)** — подготовка окружения для теста в pytest.
- **Swagger UI** — интерактивная документация API, сгенерированная из кода.

---

## 10. Куда расти дальше

- Аутентификация (JWT) и роли
- Пагинация, фильтрация и сортировка в списках
- Сложные транзакции (например, «оформить заказ» = списать stock + создать заказ)
- Логирование, обработка ошибок (middleware), rate limiting
- CI: запуск тестов и миграций в GitHub Actions
- Модели SQLAlchemy + `alembic revision --autogenerate` вместо ручного SQL
