"""Работа с PostgreSQL через asyncpg.

asyncpg — низкоуровневый асинхронный драйвер: мы пишем SQL руками,
а пул соединений живёт на всём приложении.
"""

import asyncpg
from fastapi import Request

from app.config import get_settings


def _asyncpg_dsn() -> str:
    """asyncpg не понимает префикс `postgresql+asyncpg://` — убираем его."""
    return get_settings().database_url.replace("+asyncpg", "")


async def create_pool() -> asyncpg.Pool:
    """Создаёт пул соединений к базе данных."""
    return await asyncpg.create_pool(dsn=_asyncpg_dsn(), min_size=1, max_size=10)


async def get_pool(request: Request) -> asyncpg.Pool:
    """FastAPI-зависимость: отдаёт пул из состояния приложения."""
    return request.app.state.pool
