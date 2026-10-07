"""Тесты эндпоинтов корзины."""

from decimal import Decimal


async def test_full_cart_flow(client):
    await client.post("/users", json={"username": "ivan", "email": "ivan@example.com"})
    await client.post("/products", json={"name": "Мышь", "price": "100.00", "stock": 10})
    await client.post("/products", json={"name": "Клавиатура", "price": "250.50", "stock": 5})

    # добавляем два разных товара
    response = await client.post("/cart/1/items", json={"product_id": 1, "quantity": 2})
    assert response.status_code == 201
    assert Decimal(str(response.json()["total"])) == Decimal("200.00")

    response = await client.post("/cart/1/items", json={"product_id": 2, "quantity": 1})
    assert response.status_code == 201

    # повторное добавление того же товара увеличивает количество
    response = await client.post("/cart/1/items", json={"product_id": 1, "quantity": 1})
    assert response.status_code == 201
    assert response.json()["quantity"] == 3

    # смотрим всю корзину
    response = await client.get("/cart/1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    # 3 * 100.00 + 1 * 250.50 = 550.50
    assert Decimal(str(data["total"])) == Decimal("550.50")

    # изменяем количество
    response = await client.put("/cart/1/items/1", json={"quantity": 5})
    assert response.status_code == 200
    assert response.json()["quantity"] == 5

    # удаляем товар
    response = await client.delete("/cart/1/items/1")
    assert response.status_code == 204

    response = await client.get("/cart/1")
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["product_id"] == 2


async def test_add_to_cart_unknown_user(client):
    response = await client.post("/cart/999/items", json={"product_id": 1})
    assert response.status_code == 404


async def test_add_to_cart_unknown_product(client):
    await client.post("/users", json={"username": "ivan", "email": "ivan@example.com"})
    response = await client.post("/cart/1/items", json={"product_id": 999})
    assert response.status_code == 404


async def test_add_to_cart_not_enough_stock(client):
    await client.post("/users", json={"username": "ivan", "email": "ivan@example.com"})
    await client.post("/products", json={"name": "Мышь", "price": "100.00", "stock": 2})

    response = await client.post("/cart/1/items", json={"product_id": 1, "quantity": 3})
    assert response.status_code == 400


async def test_update_cart_item_not_in_cart(client):
    await client.post("/users", json={"username": "ivan", "email": "ivan@example.com"})
    await client.post("/products", json={"name": "Мышь", "price": "100.00", "stock": 10})

    response = await client.put("/cart/1/items/1", json={"quantity": 3})
    assert response.status_code == 404


async def test_get_cart_unknown_user(client):
    response = await client.get("/cart/999")
    assert response.status_code == 404
