# tests/test_auth.py
import pytest

TEST_EMAIL = "auth_test_user_spazio@spazio.com"
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
async def test_login_user(async_client):
    """Prueba el inicio de sesión y la obtención del token JWT."""
    response = await async_client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client):
    """Prueba que el login falle con contraseña incorrecta."""
    response = await async_client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": "WrongPassword"}
    )
    assert response.status_code == 401


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
