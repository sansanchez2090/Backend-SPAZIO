# tests/conftest.py
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.database import get_db
from app.core.config import settings

# Usamos NullPool para que cada test abra su propia conexión limpia sin reutilizar un pool compartido
engine_test = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # <--- CLAVE: Evita el error de "another operation is in progress" en asyncpg
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
