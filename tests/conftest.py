# tests/conftest.py
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.database import get_db
from app.core.config import settings
from app.models.availability import Availability
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.space import Space
from app.models.user import User
from tests.helpers import (
    EMAIL_DOMAIN,
    LOGIN_URL,
    REGISTER_URL,
    BOOKINGS_URL,
    PAYMENTS_URL,
    SPACES_URL,
    bearer,
    booking_payload,
    build_space_payload,
    build_user_payload,
    create_bookable_space,
    payment_payload,
    slot,
)

# Usamos NullPool para que cada test abra su propia conexión limpia sin reutilizar un pool compartido
engine_test = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # evita "another operation is in progress" en asyncpg
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
)

TestingSessionLocal = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


# --------------------------------------------------------------------------- #
# Infraestructura
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture(scope="function")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP asíncrono para probar los endpoints de FastAPI."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Sesión directa a BD para verificar o manipular el estado persistido."""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def cleanup_qa_users():
    """Tras cada test borra todo lo creado por la suite (usuarios qa_*@pytest-qa.com).
    Orden: pagos → reservas → disponibilidades → espacios → usuarios (las FK de bookings
    no tienen ON DELETE CASCADE)."""
    yield
    async with TestingSessionLocal() as session:
        qa_users = select(User.id).where(
            User.email.like(f"qa\\_%@{EMAIL_DOMAIN}", escape="\\")
        )
        qa_spaces = select(Space.id).where(Space.host_id.in_(qa_users))
        qa_bookings = select(Booking.id).where(
            or_(Booking.user_id.in_(qa_users), Booking.space_id.in_(qa_spaces))
        )
        await session.execute(
            delete(Payment).where(Payment.booking_id.in_(qa_bookings))
        )
        await session.execute(delete(Booking).where(Booking.id.in_(qa_bookings)))
        await session.execute(
            delete(Availability).where(Availability.space_id.in_(qa_spaces))
        )
        await session.execute(delete(Space).where(Space.id.in_(qa_spaces)))
        await session.execute(delete(User).where(User.id.in_(qa_users)))
        await session.commit()


# --------------------------------------------------------------------------- #
# Usuarios
# --------------------------------------------------------------------------- #
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
async def other_guest(async_client) -> dict:
    return await _register_and_login(async_client, is_host=False)


# --------------------------------------------------------------------------- #
# Espacios, reservas y pagos
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def space(async_client, host) -> dict:
    """Espacio ya publicado por `host`, SIN periodos de disponibilidad."""
    r = await async_client.post(
        SPACES_URL, json=build_space_payload(), headers=host["headers"]
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest_asyncio.fixture
async def bookable_space(async_client, host) -> dict:
    """Espacio de $10.000/h con disponibilidad desde ayer hasta dentro de 10 días."""
    return await create_bookable_space(async_client, host["headers"])


@pytest_asyncio.fixture
async def pending_booking(async_client, bookable_space, guest) -> dict:
    """Reserva PENDING_PAYMENT de 2 h (20.000) dentro de 3 días, hecha por `guest`."""
    start, end = slot()
    r = await async_client.post(
        BOOKINGS_URL,
        json=booking_payload(bookable_space["id"], start, end),
        headers=guest["headers"],
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest_asyncio.fixture
async def confirmed_booking(async_client, pending_booking, guest) -> dict:
    r = await async_client.post(
        PAYMENTS_URL,
        json=payment_payload(pending_booking["id"]),
        headers=guest["headers"],
    )
    assert r.status_code == 200, r.text
    return {**pending_booking, "status": "CONFIRMED"}


@pytest_asyncio.fixture
async def expire_lock(db_session):
    """Devuelve una función que vence la retención de 10 min de una reserva."""

    async def _expire(booking_id: str):
        await db_session.execute(
            update(Booking)
            .where(Booking.id == uuid.UUID(booking_id))
            .values(locked_until=datetime.now(timezone.utc) - timedelta(minutes=1))
        )
        await db_session.commit()

    return _expire
