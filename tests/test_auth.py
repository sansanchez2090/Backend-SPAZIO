# tests/test_auth.py  (versión esencial)
import uuid
from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import settings
from tests.helpers import LOGIN_URL, ME_URL, bearer, make_token

pytestmark = pytest.mark.asyncio


class TestLogin:
    async def test_login_success_and_token_works(self, async_client, registered_user):
        r = await async_client.post(
            LOGIN_URL,
            json={
                "email": registered_user["email"],
                "password": registered_user["password"],
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["token_type"] == "bearer"

        payload = jwt.decode(
            body["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        assert payload["sub"] == registered_user["id"]
        assert "exp" in payload

        me = await async_client.get(ME_URL, headers=bearer(body["access_token"]))
        assert me.status_code == 200

    async def test_wrong_password_returns_401(self, async_client, registered_user):
        r = await async_client.post(
            LOGIN_URL,
            json={"email": registered_user["email"], "password": "WrongPass123"},
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "Correo o contraseña incorrectos"

    async def test_unknown_email_returns_same_401(self, async_client, registered_user):
        wrong_pw = await async_client.post(
            LOGIN_URL,
            json={"email": registered_user["email"], "password": "WrongPass123"},
        )
        unknown = await async_client.post(
            LOGIN_URL,
            json={"email": "nadie_qa@pytest-qa.com", "password": "WrongPass123"},
        )
        assert unknown.status_code == 401
        assert unknown.json() == wrong_pw.json()  # no permite enumerar usuarios

    @pytest.mark.parametrize(
        "payload",
        [{}, {"email": "a@b.com"}, {"email": "no-es-email", "password": "Str0ngPass!"}],
    )
    async def test_invalid_payload_returns_422(self, async_client, payload):
        r = await async_client.post(LOGIN_URL, json=payload)
        assert r.status_code == 422


class TestJWTValidation:
    async def test_no_token_is_rejected(self, async_client):
        r = await async_client.get(ME_URL)
        assert r.status_code in (401, 403)  # 403 en FastAPI antiguo, 401 en nuevo

    async def test_garbage_token_returns_401(self, async_client):
        r = await async_client.get(ME_URL, headers=bearer("esto.no.es.un.jwt"))
        assert r.status_code == 401

    async def test_expired_token_returns_401(self, async_client, registered_user):
        token = make_token(registered_user["id"], expires_delta=timedelta(seconds=-60))
        r = await async_client.get(ME_URL, headers=bearer(token))
        assert r.status_code == 401

    async def test_wrong_secret_returns_401(self, async_client, registered_user):
        token = make_token(registered_user["id"], secret="otra-clave-distinta")
        r = await async_client.get(ME_URL, headers=bearer(token))
        assert r.status_code == 401

    async def test_token_for_nonexistent_user_returns_401(self, async_client):
        r = await async_client.get(ME_URL, headers=bearer(make_token(uuid.uuid4())))
        assert r.status_code == 401

    async def test_token_with_non_uuid_sub_returns_401(self, async_client):
        r = await async_client.get(ME_URL, headers=bearer(make_token("no-soy-un-uuid")))
        assert r.status_code == 401

    async def test_token_without_sub_returns_401(self, async_client):
        r = await async_client.get(ME_URL, headers=bearer(make_token(None)))
        assert r.status_code == 401
