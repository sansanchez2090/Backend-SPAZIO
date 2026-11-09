# tests/conftest.py
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from tests.helpers import (
    EMAIL_DOMAIN,
    LOGIN_URL,
    REGISTER_URL,
    bearer,
    build_user_payload,
    SPACES_URL,
    build_space_payload,
)

engine_test = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
)

TestingSessionLocal = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="function")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP asíncrono para probar los endpoints de FastAPI."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Sesión directa a BD para verificar el estado persistido."""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def cleanup_qa_users():
    """Tras cada test borra todos los usuarios creados por la suite (qa_*@pytest-qa.com)."""
    yield
    async with TestingSessionLocal() as session:
        await session.execute(
            delete(User).where(User.email.like(f"qa\\_%@{EMAIL_DOMAIN}", escape="\\"))
        )
        await session.commit()


@pytest_asyncio.fixture
async def registered_user(async_client: AsyncClient) -> dict:
    """Usuario ya registrado. Devuelve la respuesta de la API + 'password' en claro."""
    payload = build_user_payload()
    r = await async_client.post(REGISTER_URL, json=payload)
    assert r.status_code == 201, r.text
    return {**r.json(), "password": payload["password"]}


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, registered_user: dict) -> dict:
    r = await async_client.post(
        LOGIN_URL,
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert r.status_code == 200, r.text
    return bearer(r.json()["access_token"])


async def _register_and_login(client, is_host: bool) -> dict:
    payload = build_user_payload(is_host=is_host)
    r = await client.post(REGISTER_URL, json=payload)
    assert r.status_code == 201, r.text
    login = await client.post(
        LOGIN_URL, json={"email": payload["email"], "password": payload["password"]}
    )
    assert login.status_code == 200, login.text
    return {"id": r.json()["id"], "headers": bearer(login.json()["access_token"])}


@pytest_asyncio.fixture
async def host(async_client) -> dict:
    """Anfitrión autenticado: {'id': ..., 'headers': ...}"""
    return await _register_and_login(async_client, is_host=True)


@pytest_asyncio.fixture
async def other_host(async_client) -> dict:
    return await _register_and_login(async_client, is_host=True)


@pytest_asyncio.fixture
async def guest(async_client) -> dict:
    """Usuario normal (is_host=False)."""
    return await _register_and_login(async_client, is_host=False)


@pytest_asyncio.fixture
async def space(async_client, host) -> dict:
    """Espacio ya publicado por `host`."""
    r = await async_client.post(
        SPACES_URL, json=build_space_payload(), headers=host["headers"]
    )
    assert r.status_code == 201, r.text
    return r.json()
