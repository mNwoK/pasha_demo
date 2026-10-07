"""Общие фикстуры для тестов.

Схема работы:
1. Один раз на сессию: создаём тестовую БД (если её нет) и применяем миграции Alembic.
2. На каждый тест: создаём пул asyncpg, очищаем таблицы, поднимаем HTTP-клиент.
"""

import asyncio
import os
import subprocess
import sys

import asyncpg
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient

from app.main import app

load_dotenv()

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/shop_test"
)

# asyncpg не понимает суффикс драйвера
TEST_DSN = TEST_DATABASE_URL.replace("+asyncpg", "")


def _admin_dsn() -> str:
    """DSN к служебной базе postgres — нужна для CREATE DATABASE."""
    base, dbname = TEST_DSN.rstrip("/").rsplit("/", 1)
    return f"{base}/postgres", dbname


@pytest.fixture(scope="session", autouse=True)
def prepare_test_db():
    """Создаёт тестовую БД и применяет миграции один раз на всю сессию."""
    async def _create_database() -> None:
        admin_dsn, dbname = _admin_dsn()
        conn = await asyncpg.connect(admin_dsn)
        try:
            exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", dbname)
            if not exists:
                await conn.execute(f'CREATE DATABASE "{dbname}"')
        finally:
            await conn.close()

    import asyncio

    asyncio.run(_create_database())

    # Alembic читет URL из переменной окружения DATABASE_URL
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    yield


@pytest_asyncio.fixture
async def pool():
    """Пул соединений с очисткой таблиц до и после каждого теста."""
    pool = await asyncpg.create_pool(dsn=TEST_DSN, min_size=1, max_size=5)
    await pool.execute("TRUNCATE cart_items, products, users RESTART IDENTITY CASCADE")
    yield pool
    await pool.execute("TRUNCATE cart_items, products, users RESTART IDENTITY CASCADE")
    await pool.close()


@pytest_asyncio.fixture
async def client(pool) -> AsyncClient:
    """HTTP-клиент, обращающийся к приложению напрямую (без сети).

    Lifespan приложения здесь не запускается, поэтому пул ставим вручную.
    """
    app.state.pool = pool
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
