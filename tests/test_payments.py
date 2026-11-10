# tests/test_payments.py  (versión mínima)
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.payment import Payment
from tests.helpers import PAYMENTS_URL, booking_url, cancel_url, payment_payload

pytestmark = pytest.mark.asyncio


async def pay(client, user, booking_id, simulated_status="APPROVED"):
    return await client.post(
        PAYMENTS_URL,
        json=payment_payload(booking_id, simulated_status),
        headers=user["headers"],
    )


async def booking_status(client, user, booking_id) -> str:
    r = await client.get(booking_url(booking_id), headers=user["headers"])
    return r.json()["status"]


async def test_approved_payment_confirms_booking(
    async_client, pending_booking, guest, db_session
):
    r = await pay(async_client, guest, pending_booking["id"])

    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"
    assert (
        await booking_status(async_client, guest, pending_booking["id"]) == "CONFIRMED"
    )

    payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.booking_id == uuid.UUID(pending_booking["id"])
            )
        )
    ).scalar_one()
    assert payment.amount == Decimal(str(pending_booking["total_amount"]))


async def test_rejected_payment_can_be_retried_while_lock_is_valid(
    async_client, pending_booking, guest
):
    rejected = await pay(async_client, guest, pending_booking["id"], "REJECTED")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert (
        await booking_status(async_client, guest, pending_booking["id"])
        == "PENDING_PAYMENT"
    )

    retry = await pay(async_client, guest, pending_booking["id"], "APPROVED")
    assert retry.status_code == 200
    assert retry.json()["status"] == "APPROVED"
    assert (
        await booking_status(async_client, guest, pending_booking["id"]) == "CONFIRMED"
    )


async def test_cannot_pay_confirmed_booking_again(
    async_client, confirmed_booking, guest
):
    r = await pay(async_client, guest, confirmed_booking["id"])
    assert r.status_code == 400


async def test_cannot_pay_cancelled_booking(async_client, pending_booking, guest):
    await async_client.post(cancel_url(pending_booking["id"]), headers=guest["headers"])
    r = await pay(async_client, guest, pending_booking["id"])
    assert r.status_code == 400


async def test_expired_lock_returns_400_and_expires_booking(
    async_client, pending_booking, guest, expire_lock
):
    await expire_lock(pending_booking["id"])
    r = await pay(async_client, guest, pending_booking["id"])
    assert r.status_code == 400
    assert await booking_status(async_client, guest, pending_booking["id"]) == "EXPIRED"


async def test_cannot_pay_someone_elses_booking(
    async_client, pending_booking, other_guest
):
    r = await pay(async_client, other_guest, pending_booking["id"])
    assert r.status_code == 404


async def test_requires_authentication(async_client, pending_booking):
    r = await async_client.post(
        PAYMENTS_URL, json=payment_payload(pending_booking["id"])
    )
    assert r.status_code in (401, 403)


async def test_unknown_simulated_status_is_rejected(
    async_client, pending_booking, guest
):
    r = await pay(async_client, guest, pending_booking["id"], "FOO")
    assert r.status_code == 422
