"""Эндпоинты корзины: добавление, просмотр, изменение и удаление товаров.

Таблица cart_items связывает пользователя и товар (составной первичный ключ),
поэтому одного товара в корзине может быть только одна строка —
повторное добавление увеличивает quantity.
"""

from decimal import Decimal

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_pool
from app.schemas import CartItemAdd, CartItemRead, CartItemUpdate, CartRead

router = APIRouter()


async def _require_user(pool: Pool, user_id: int) -> None:
    """Проверяет существование пользователя, иначе 404."""
    user = await pool.fetchrow("SELECT id FROM users WHERE id = $1", user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")


async def _get_cart_item(pool: Pool, user_id: int, product_id: int) -> CartItemRead:
    """Отдаёт одну позицию корзины с подсчитанной стоимостью."""
    row = await pool.fetchrow(
        """
        SELECT ci.product_id, p.name, p.price, ci.quantity,
               (p.price * ci.quantity) AS total
        FROM cart_items ci
        JOIN products p ON p.id = ci.product_id
        WHERE ci.user_id = $1 AND ci.product_id = $2
        """,
        user_id,
        product_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден в корзине",
        )
    return CartItemRead.model_validate(dict(row))


@router.post(
    "/{user_id}/items",
    response_model=CartItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить товар в корзину",
)
async def add_to_cart(
    user_id: int, payload: CartItemAdd, pool: Pool = Depends(get_pool)
) -> CartItemRead:
    await _require_user(pool, user_id)

    product = await pool.fetchrow(
        "SELECT id, stock FROM products WHERE id = $1", payload.product_id
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    if payload.quantity > product["stock"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно товара на складе",
        )

    # Если позиция уже есть — увеличиваем количество, иначе вставляем новую
    await pool.execute(
        """
        INSERT INTO cart_items (user_id, product_id, quantity)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, product_id)
        DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
        """,
        user_id,
        payload.product_id,
        payload.quantity,
    )
    return await _get_cart_item(pool, user_id, payload.product_id)


@router.get("/{user_id}", response_model=CartRead, summary="Получить корзину")
async def get_cart(user_id: int, pool: Pool = Depends(get_pool)) -> CartRead:
    await _require_user(pool, user_id)

    rows = await pool.fetch(
        """
        SELECT ci.product_id, p.name, p.price, ci.quantity,
               (p.price * ci.quantity) AS total
        FROM cart_items ci
        JOIN products p ON p.id = ci.product_id
        WHERE ci.user_id = $1
        ORDER BY ci.product_id
        """,
        user_id,
    )
    items = [CartItemRead.model_validate(dict(row)) for row in rows]
    total = sum((item.total for item in items), Decimal(0))
    return CartRead(user_id=user_id, items=items, total=total)


@router.put(
    "/{user_id}/items/{product_id}",
    response_model=CartItemRead,
    summary="Изменить количество товара в корзине",
)
async def update_cart_item(
    user_id: int,
    product_id: int,
    payload: CartItemUpdate,
    pool: Pool = Depends(get_pool),
) -> CartItemRead:
    await _require_user(pool, user_id)

    product = await pool.fetchrow(
        "SELECT id, stock FROM products WHERE id = $1", product_id
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    if payload.quantity > product["stock"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно товара на складе",
        )

    result = await pool.execute(
        """
        UPDATE cart_items SET quantity = $3
        WHERE user_id = $1 AND product_id = $2
        """,
        user_id,
        product_id,
        payload.quantity,
    )
    # pool.execute() возвращает тег вида "UPDATE 0" — число после команды
    if result.split()[-1] == "0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден в корзине",
        )
    return await _get_cart_item(pool, user_id, product_id)


@router.delete(
    "/{user_id}/items/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить товар из корзины",
)
async def remove_from_cart(
    user_id: int, product_id: int, pool: Pool = Depends(get_pool)
) -> None:
    await _require_user(pool, user_id)
    await pool.execute(
        "DELETE FROM cart_items WHERE user_id = $1 AND product_id = $2",
        user_id,
        product_id,
    )
