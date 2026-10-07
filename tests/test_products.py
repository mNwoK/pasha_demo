"""Тесты эндпоинтов товаров."""

from decimal import Decimal


async def test_create_product(client):
    response = await client.post(
        "/products",
        json={"name": "Мышь", "description": "Беспроводная", "price": "1499.99", "stock": 10},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Мышь"
    assert Decimal(str(data["price"])) == Decimal("1499.99")
    assert data["stock"] == 10


async def test_create_product_validation_error(client):
    response = await client.post("/products", json={"name": "Мышь", "price": "-1"})  # цена < 0
    assert response.status_code == 422

    response = await client.post("/products", json={"name": "", "price": "1.00"})  # пустое имя
    assert response.status_code == 422


async def test_get_product(client):
    await client.post("/products", json={"name": "Мышь", "price": "1499.99", "stock": 10})

    response = await client.get("/products/1")
    assert response.status_code == 200
    assert response.json()["name"] == "Мышь"


async def test_get_unknown_product(client):
    response = await client.get("/products/999")
    assert response.status_code == 404


async def test_list_products(client):
    for i in range(3):
        await client.post("/products", json={"name": f"Товар {i}", "price": f"{i + 1}.00"})

    response = await client.get("/products")
    assert response.status_code == 200
    assert len(response.json()) == 3
