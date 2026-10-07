"""Эндпоинты для товаров."""

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_pool
from app.schemas import ProductCreate, ProductRead

router = APIRouter()


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать товар",
)
async def create_product(
    payload: ProductCreate, pool: Pool = Depends(get_pool)
) -> ProductRead:
    row = await pool.fetchrow(
        """
        INSERT INTO products (name, description, price, stock)
        VALUES ($1, $2, $3, $4)
        RETURNING id, name, description, price, stock
        """,
        payload.name,
        payload.description,
        payload.price,
        payload.stock,
    )
    return ProductRead.model_validate(dict(row))


@router.get("", response_model=list[ProductRead], summary="Список товаров")
async def list_products(
    limit: int = 100,
    offset: int = 0,
    pool: Pool = Depends(get_pool),
) -> list[ProductRead]:
    rows = await pool.fetch(
        "SELECT id, name, description, price, stock FROM products ORDER BY id LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    return [ProductRead.model_validate(dict(row)) for row in rows]


@router.get("/{product_id}", response_model=ProductRead, summary="Получить товар")
async def get_product(product_id: int, pool: Pool = Depends(get_pool)) -> ProductRead:
    row = await pool.fetchrow(
        "SELECT id, name, description, price, stock FROM products WHERE id = $1",
        product_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    return ProductRead.model_validate(dict(row))
