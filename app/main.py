"""Точка входа приложения: создаём FastAPI и подключаем роутеры."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.database import create_pool
from app.routers import cart, products, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan — код, который выполняется при старте и остановке приложения.

    Аналог старого @app.on_event("startup"/"shutdown"), но актуальный способ.
    """
    app.state.pool = await create_pool()  # открываем пул соединений
    yield
    await app.state.pool.close()  # закрываем пул при остановке


def create_app() -> FastAPI:
    """Фабрика приложения — удобно для тестов и для переиспользования."""
    settings = get_settings()

    # /docs и /redoc — Swagger UI и ReDoc, FastAPI генерирует их сам
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Минимальный пример интернет-магазина на FastAPI. "
            "Пользователи, товары и корзины. "
            "БД — PostgreSQL, доступ через asyncpg, миграции — Alembic."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.include_router(users.router, prefix="/users", tags=["Пользователи"])
    app.include_router(products.router, prefix="/products", tags=["Товары"])
    app.include_router(cart.router, prefix="/cart", tags=["Корзина"])

    @app.get("/healthz", tags=["Сервис"], summary="Проверка работоспособности")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
