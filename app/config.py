"""Настройки приложения: читаются из переменных окружения и файла .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # pydantic-settings сам подхватывает .env и переменные окружения
    # extra="ignore" — другие переменные (например, TEST_DATABASE_URL) не ломают настройки
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # URL вида postgresql+asyncpg://user:password@host:port/dbname
    # Такой формат понимает SQLAlchemy/Alembic; asyncpg принимает его без суффикса драйвера
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/shop"

    app_name: str = "Shop API"


@lru_cache
def get_settings() -> Settings:
    """Кэшируем настройки, чтобы не читать окружение на каждый запрос."""
    return Settings()
