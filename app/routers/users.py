"""Эндпоинты для пользователей."""

from asyncpg import Pool, UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_pool
from app.schemas import UserCreate, UserRead

router = APIRouter()


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать пользователя",
)
async def create_user(payload: UserCreate, pool: Pool = Depends(get_pool)) -> UserRead:
    try:
        row = await pool.fetchrow(
            """
            INSERT INTO users (username, email)
            VALUES ($1, $2)
            RETURNING id, username, email, created_at
            """,
            payload.username,
            payload.email,
        )
    except UniqueViolationError:
        # asyncpg кидает при нарушении UNIQUE-ограничений в БД
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже существует",
        )
    return UserRead.model_validate(dict(row))


@router.get("", response_model=list[UserRead], summary="Список пользователей")
async def list_users(
    limit: int = 100,
    offset: int = 0,
    pool: Pool = Depends(get_pool),
) -> list[UserRead]:
    rows = await pool.fetch(
        "SELECT id, username, email, created_at FROM users ORDER BY id LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    return [UserRead.model_validate(dict(row)) for row in rows]


@router.get("/{user_id}", response_model=UserRead, summary="Получить пользователя")
async def get_user(user_id: int, pool: Pool = Depends(get_pool)) -> UserRead:
    row = await pool.fetchrow(
        "SELECT id, username, email, created_at FROM users WHERE id = $1", user_id
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return UserRead.model_validate(dict(row))
