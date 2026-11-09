# tests/test_user.py
import pytest

TEST_EMAIL = "test_user_spazio@spazio.com"
TEST_PASSWORD = "PasswordSeguro123"


@pytest.mark.asyncio
async def test_register_user(async_client):
    """Prueba el registro exitoso de un nuevo usuario."""
    response = await async_client.post(
        "/api/v1/users/register",
        json={
            "full_name": "Test User",
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "is_host": True,
        },
    )
    assert response.status_code in [200, 201]
    data = response.json()
    assert data["email"] == TEST_EMAIL
    assert "id" in data


@pytest.mark.asyncio
async def test_get_current_user_me(async_client):
    """Prueba el endpoint protegido /me usando el token JWT."""
    # 1. Hacemos login para obtener el token
    login_response = await async_client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    token = login_response.json()["access_token"]

    # 2. Hacemos la petición al endpoint protegido enviando el Bearer Token
    response = await async_client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_EMAIL


@pytest.mark.asyncio
async def test_update_user_me(async_client):
    """Prueba la actualización de datos del usuario autenticado."""
    login_response = await async_client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    token = login_response.json()["access_token"]

    response = await async_client.put(
        "/api/v1/users/me",
        json={"full_name": "Updated Test User"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Test User"


@pytest.mark.asyncio
async def test_delete_user_me(async_client):
    """Prueba la eliminación de la cuenta del usuario (limpieza de BD)."""
    login_response = await async_client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    token = login_response.json()["access_token"]

    response = await async_client.delete(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204
