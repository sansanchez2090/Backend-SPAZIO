# tests/test_bookings.py
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.models.booking import Booking
from app.models.payment import Payment
from tests.helpers import (
    AVAIL_URL,
    BOOKINGS_ME_URL,
    BOOKINGS_URL,
    PAYMENTS_URL,
    booking_payload,
    booking_url,
    cancel_url,
    parse_dt,
    payment_payload,
    slot,
    space_url,
)

pytestmark = pytest.mark.asyncio


async def book(client, user, space_id, start, end):
    return await client.post(
        BOOKINGS_URL,
        json=booking_payload(space_id, start, end),
        headers=user["headers"],
    )


# --------------------------------------------------------------------------- #
# Crear y consultar
# --------------------------------------------------------------------------- #
async def test_create_booking_calculates_amount_and_lock(
    async_client, bookable_space, guest
):
    start, end = slot(hours=2)
    r = await book(async_client, guest, bookable_space["id"], start, end)

    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "PENDING_PAYMENT"
    assert b["user_id"] == guest["id"]
    assert Decimal(str(b["total_amount"])) == Decimal("20000")  # 2 h × 10.000
    remaining = parse_dt(b["locked_until"]) - datetime.now(timezone.utc)
    assert timedelta(minutes=9) < remaining <= timedelta(minutes=10)


async def test_outside_availability_returns_400(async_client, bookable_space, guest):
    start, end = slot(
        offset=timedelta(days=30)
    )  # la disponibilidad solo llega a +10 días
    r = await book(async_client, guest, bookable_space["id"], start, end)
    assert r.status_code == 400


async def test_non_whole_hours_returns_422(async_client, bookable_space, guest):
    start = (datetime.now(timezone.utc) + timedelta(days=3)).replace(
        minute=30, second=0, microsecond=0
    )
    r = await book(
        async_client,
        guest,
        bookable_space["id"],
        start.isoformat(),
        (start + timedelta(hours=2)).isoformat(),
    )
    assert r.status_code == 422


async def test_past_dates_are_rejected(async_client, host, bookable_space, guest):
    # Reserva que empieza en el pasado
    start, end = slot(offset=timedelta(days=-1))
    booking = await book(async_client, guest, bookable_space["id"], start, end)
    assert booking.status_code == 422

    # Periodo de disponibilidad que ya terminó
    now = datetime.now(timezone.utc)
    availability = await async_client.post(
        AVAIL_URL,
        json={
            "space_id": bookable_space["id"],
            "start_time": (now - timedelta(days=3)).isoformat(),
            "end_time": (now - timedelta(days=2)).isoformat(),
        },
        headers=host["headers"],
    )
    assert availability.status_code == 422


async def test_booking_detail_only_visible_to_owner(
    async_client, pending_booking, guest, other_guest
):
    ok = await async_client.get(
        booking_url(pending_booking["id"]), headers=guest["headers"]
    )
    other = await async_client.get(
        booking_url(pending_booking["id"]), headers=other_guest["headers"]
    )
    assert ok.status_code == 200 and ok.json()["id"] == pending_booking["id"]
    assert other.status_code == 404


# --------------------------------------------------------------------------- #
# Conflictos y retención (RF-07)
# --------------------------------------------------------------------------- #
async def test_same_slot_blocked_while_pending(
    async_client, bookable_space, pending_booking, other_guest
):
    r = await book(
        async_client,
        other_guest,
        bookable_space["id"],
        pending_booking["start_time"],
        pending_booking["end_time"],
    )
    assert r.status_code == 409


async def test_slot_is_free_after_lock_expires(
    async_client, bookable_space, pending_booking, other_guest, expire_lock
):
    await expire_lock(pending_booking["id"])
    r = await book(
        async_client,
        other_guest,
        bookable_space["id"],
        pending_booking["start_time"],
        pending_booking["end_time"],
    )
    assert r.status_code == 201


async def test_unpaid_booking_becomes_expired_when_lock_runs_out(
    async_client, pending_booking, guest, expire_lock
):
    await expire_lock(pending_booking["id"])
    detail = await async_client.get(
        booking_url(pending_booking["id"]), headers=guest["headers"]
    )
    assert detail.json()["status"] == "EXPIRED"


async def test_concurrent_bookings_for_same_slot_only_one_wins(
    async_client, bookable_space, guest, other_guest
):
    start, end = slot()
    r1, r2 = await asyncio.gather(
        book(async_client, guest, bookable_space["id"], start, end),
        book(async_client, other_guest, bookable_space["id"], start, end),
    )
    assert sorted([r1.status_code, r2.status_code]) == [201, 409]


# --------------------------------------------------------------------------- #
# Mis reservas y cancelación (RF-15 / RF-08)
# --------------------------------------------------------------------------- #
async def test_list_my_bookings_shows_cancellable_flag_and_refund(
    async_client, confirmed_booking, guest
):
    r = await async_client.get(BOOKINGS_ME_URL, headers=guest["headers"])
    assert r.status_code == 200
    item = {b["id"]: b for b in r.json()}[confirmed_booking["id"]]
    assert item["status"] == "CONFIRMED"
    assert item["is_cancellable"] is True  # CONFIRMED y faltan más de 24 h
    assert item["refund_percentage"] == 100
    assert Decimal(str(item["refund_amount"])) == Decimal(
        str(confirmed_booking["total_amount"])
    )


async def test_cancel_pending_booking(async_client, pending_booking, guest):
    r = await async_client.post(
        cancel_url(pending_booking["id"]), headers=guest["headers"]
    )
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"
    assert r.json()["cancelled_at"] is not None


async def test_cancel_confirmed_more_than_24h_refunds_100_percent(
    async_client, confirmed_booking, guest, db_session
):
    r = await async_client.post(
        cancel_url(confirmed_booking["id"]), headers=guest["headers"]
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "CANCELLED"
    assert body["refund_percentage"] == 100
    assert Decimal(str(body["refund_amount"])) == Decimal(
        str(confirmed_booking["total_amount"])
    )

    payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.booking_id == uuid.UUID(confirmed_booking["id"])
            )
        )
    ).scalar_one()
    assert payment.status.value == "REFUNDED"
    assert payment.refund_amount == Decimal(str(confirmed_booking["total_amount"]))


async def test_cancel_confirmed_less_than_24h_applies_0_percent_refund(
    async_client, bookable_space, guest, other_guest, db_session
):
    start, end = slot(offset=timedelta(hours=2), hours=1)  # empieza en < 24 h
    created = (await book(async_client, guest, bookable_space["id"], start, end)).json()
    await async_client.post(
        PAYMENTS_URL, json=payment_payload(created["id"]), headers=guest["headers"]
    )

    r = await async_client.post(cancel_url(created["id"]), headers=guest["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "CANCELLED"
    assert body["refund_percentage"] == 0
    assert Decimal(str(body["refund_amount"])) == Decimal("0")

    payment = (
        await db_session.execute(
            select(Payment).where(Payment.booking_id == uuid.UUID(created["id"]))
        )
    ).scalar_one()
    assert payment.refund_amount == Decimal("0")

    # El periodo queda libre para otro usuario
    again = await book(
        async_client,
        other_guest,
        bookable_space["id"],
        created["start_time"],
        created["end_time"],
    )
    assert again.status_code == 201


async def test_cannot_cancel_after_period_started(
    async_client, confirmed_booking, guest, db_session
):
    now = datetime.now(timezone.utc)
    await db_session.execute(
        update(Booking)
        .where(Booking.id == uuid.UUID(confirmed_booking["id"]))
        .values(start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=1))
    )
    await db_session.commit()

    r = await async_client.post(
        cancel_url(confirmed_booking["id"]), headers=guest["headers"]
    )
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Integridad
# --------------------------------------------------------------------------- #
async def test_cannot_delete_space_with_confirmed_booking(
    async_client, host, bookable_space, confirmed_booking, guest
):
    r = await async_client.delete(
        space_url(bookable_space["id"]), headers=host["headers"]
    )
    assert r.status_code == 409

    assert (await async_client.get(space_url(bookable_space["id"]))).status_code == 200
    detail = await async_client.get(
        booking_url(confirmed_booking["id"]), headers=guest["headers"]
    )
    assert detail.json()["status"] == "CONFIRMED"
