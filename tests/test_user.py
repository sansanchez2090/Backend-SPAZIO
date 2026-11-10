# tests/test_users.py
import uuid

import pytest
from sqlalchemy import select

from app.core.security import verify_password
from app.models.user import User
from tests.helpers import (
    LOGIN_URL,
    ME_URL,
    REGISTER_URL,
    build_user_payload,
    unique_email,
)

pytestmark = pytest.mark.asyncio


class TestRegister:
    async def test_register_success(self, async_client, db_session):
        payload = build_user_payload()
        r = await async_client.post(REGISTER_URL, json=payload)

        assert r.status_code == 201
        body = r.json()
        assert body["email"] == payload["email"]
        assert body["is_host"] is False
        uuid.UUID(body["id"])
        assert "password" not in body and "hashed_password" not in body

        # La contraseña se guarda hasheada
        user = (
            await db_session.execute(select(User).where(User.email == payload["email"]))
        ).scalar_one()
        assert user.hashed_password != payload["password"]
        assert verify_password(payload["password"], user.hashed_password)

    async def test_registered_user_can_login(self, async_client):
        payload = build_user_payload()
        await async_client.post(REGISTER_URL, json=payload)
        r = await async_client.post(
            LOGIN_URL, json={"email": payload["email"], "password": payload["password"]}
        )
        assert r.status_code == 200

    async def test_duplicate_email_returns_400(self, async_client):
        payload = build_user_payload()
        await async_client.post(REGISTER_URL, json=payload)
        r = await async_client.post(REGISTER_URL, json=payload)
        assert r.status_code == 400
        assert r.json()["detail"] == "El correo electrónico ya se encuentra registrado."

    @pytest.mark.parametrize(
        "overrides",
        [
            {"email": "sin-arroba"},
            {"password": "1234567"},  # 7 caracteres
            {"password": "a" * 73},  # 73 caracteres
        ],
    )
    async def test_invalid_data_returns_422(self, async_client, overrides):
        r = await async_client.post(REGISTER_URL, json=build_user_payload(**overrides))
        assert r.status_code == 422

    async def test_missing_required_field_returns_422(self, async_client):
        payload = build_user_payload()
        payload.pop("full_name")
        r = await async_client.post(REGISTER_URL, json=payload)
        assert r.status_code == 422


class TestProfile:
    async def test_get_me(self, async_client, auth_headers, registered_user):
        r = await async_client.get(ME_URL, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["id"] == registered_user["id"]
        assert r.json()["email"] == registered_user["email"]

    async def test_update_name_keeps_other_fields(
        self, async_client, auth_headers, registered_user
    ):
        r = await async_client.put(
            ME_URL, headers=auth_headers, json={"full_name": "Nuevo Nombre"}
        )
        assert r.status_code == 200
        assert r.json()["full_name"] == "Nuevo Nombre"
        assert r.json()["email"] == registered_user["email"]

    async def test_update_email_then_login_with_new_one(
        self, async_client, auth_headers, registered_user
    ):
        new_email = unique_email()
        r = await async_client.put(
            ME_URL, headers=auth_headers, json={"email": new_email}
        )
        assert r.status_code == 200

        login = await async_client.post(
            LOGIN_URL,
            json={"email": new_email, "password": registered_user["password"]},
        )
        assert login.status_code == 200

    async def test_update_password_replaces_old_one(
        self, async_client, auth_headers, registered_user
    ):
        new_password = "NuevaClave#2025"
        r = await async_client.put(
            ME_URL, headers=auth_headers, json={"password": new_password}
        )
        assert r.status_code == 200

        old = await async_client.post(
            LOGIN_URL,
            json={
                "email": registered_user["email"],
                "password": registered_user["password"],
            },
        )
        new = await async_client.post(
            LOGIN_URL,
            json={"email": registered_user["email"], "password": new_password},
        )
        assert old.status_code == 401
        assert new.status_code == 200

    @pytest.mark.parametrize("method", ["get", "put", "delete"])
    async def test_profile_requires_authentication(self, async_client, method):
        r = await getattr(async_client, method)(ME_URL)
        assert r.status_code in (401, 403)


class TestDelete:
    async def test_delete_account_full_flow(
        self, async_client, auth_headers, registered_user, db_session
    ):
        r = await async_client.delete(ME_URL, headers=auth_headers)
        assert r.status_code == 204

        # Ya no existe en BD
        user = (
            await db_session.execute(
                select(User).where(User.id == uuid.UUID(registered_user["id"]))
            )
        ).scalar_one_or_none()
        assert user is None

        # El token deja de servir y no se puede volver a iniciar sesión
        assert (await async_client.get(ME_URL, headers=auth_headers)).status_code == 401
        login = await async_client.post(
            LOGIN_URL,
            json={
                "email": registered_user["email"],
                "password": registered_user["password"],
            },
        )
        assert login.status_code == 401
