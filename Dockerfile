# syntax=docker/dockerfile:1
FROM python:3.13-slim

# Ставим uv из официального образа (аналогично `curl -LsSf https://astral.sh/uv/install.sh | sh`)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# uv ставит зависимости в /app/.venv — добавляем его в PATH
ENV PATH="/app/.venv/bin:$PATH"

# Сначала только манифесты — так слой с зависимостями кэшируется отдельно от кода
COPY pyproject.toml uv.lock ./

# Устанавливаем продакшн-зависимости (без группы dev)
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

EXPOSE 8000

# Сначала применяем миграции, потом поднимаем сервер
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
