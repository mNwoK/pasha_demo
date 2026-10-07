"""Тесты эндпоинтов пользователей."""


async def test_create_user(client):
    response = await client.post(
        "/users", json={"username": "ivan", "email": "ivan@example.com"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "ivan"
    assert data["email"] == "ivan@example.com"
    assert data["id"] == 1
    assert "created_at" in data


async def test_create_user_duplicate_email(client):
    payload = {"username": "ivan", "email": "ivan@example.com"}
    assert (await client.post("/users", json=payload)).status_code == 201

    response = await client.post("/users", json={**payload, "username": "other"})
    assert response.status_code == 409


async def test_create_user_duplicate_username(client):
    payload = {"username": "ivan", "email": "ivan@example.com"}
    assert (await client.post("/users", json=payload)).status_code == 201

    response = await client.post("/users", json={**payload, "email": "other@example.com"})
    assert response.status_code == 409


async def test_get_user(client):
    await client.post("/users", json={"username": "ivan", "email": "ivan@example.com"})

    response = await client.get("/users/1")
    assert response.status_code == 200
    assert response.json()["username"] == "ivan"


async def test_get_unknown_user(client):
    response = await client.get("/users/999")
    assert response.status_code == 404


async def test_list_users(client):
    for i in range(3):
        await client.post("/users", json={"username": f"user{i}", "email": f"u{i}@example.com"})

    response = await client.get("/users")
    assert response.status_code == 200
    assert len(response.json()) == 3

    response = await client.get("/users?limit=2")
    assert len(response.json()) == 2


async def test_create_user_validation_error(client):
    response = await client.post("/users", json={"username": "ivan"})  # нет email
    assert response.status_code == 422

    response = await client.post(
        "/users", json={"username": "ivan", "email": "not-an-email"}
    )
    assert response.status_code == 422
