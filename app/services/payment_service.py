from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
import uuid

from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentProcess, WompiCheckoutResponse
from app.services import wompi_gateway
from app.core.config import settings


async def process_simulated_payment(
    db: AsyncSession, user_id: UUID, payload: PaymentProcess
) -> Payment:
    # 1. Buscar la reserva asegurando que pertenezca al usuario
    booking_query = select(Booking).where(
        Booking.id == payload.booking_id, Booking.user_id == user_id
    )
    booking_result = await db.execute(booking_query)
    booking = booking_result.scalars().first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La reserva especificada no existe o no pertenece al usuario.",
        )

    # 2. Validar el estado de la reserva
    if booking.status == BookingStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta reserva ya se encuentra pagada y confirmada.",
        )

    if booking.status != BookingStatus.PENDING_PAYMENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede pagar una reserva en estado: {booking.status.value}",
        )

    # 3. Control estricto de expiración por los 10 minutos (RF-07)
    now = datetime.now(timezone.utc)
    if booking.locked_until < now:
        booking.status = BookingStatus.EXPIRED
        booking.cancelled_at = now
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El tiempo de retención temporal de 10 minutos ha expirado. La reserva ha sido cancelada automáticamente.",
        )

    # 4. Verificar si ya existe un registro de pago previo para esta reserva
    payment_query = select(Payment).where(Payment.booking_id == booking.id)
    payment_result = await db.execute(payment_query)
    payment = payment_result.scalars().first()

    if not payment:
        # Crear registro de pago pendiente si no existía
        payment = Payment(
            booking_id=booking.id,
            amount=booking.total_amount,
            status=PaymentStatus.PENDING,
            payment_method=payload.payment_method,
            gateway_reference=payload.gateway_reference
            or f"SIM-WOMPI-{uuid.uuid4().hex[:8]}",
        )
        db.add(payment)

    # 5. Simular aprobación o rechazo del pago según el payload del front
    if payload.simulated_status == "APPROVED":
        payment.status = PaymentStatus.APPROVED
        booking.status = BookingStatus.CONFIRMED
    else:  # REJECTED
        payment.status = PaymentStatus.REJECTED
        # RF-07: la reserva NO cambia; el usuario puede reintentar dentro de los 10 minutos.
        # Si la retención vence, el paso 3 la marca como EXPIRED.

    payment.payment_method = payload.payment_method
    if payload.gateway_reference:
        payment.gateway_reference = payload.gateway_reference

    await db.commit()
    await db.refresh(payment)
    await db.refresh(booking)

    return payment


async def _get_payable_booking(
    db: AsyncSession, user_id: UUID, booking_id: UUID
) -> Booking:
    booking_result = await db.execute(
        select(Booking).where(Booking.id == booking_id, Booking.user_id == user_id)
    )
    booking = booking_result.scalars().first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La reserva especificada no existe o no pertenece al usuario.",
        )

    if booking.status == BookingStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta reserva ya se encuentra pagada y confirmada.",
        )
    if booking.status != BookingStatus.PENDING_PAYMENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede pagar una reserva en estado: {booking.status.value}",
        )

    now = datetime.now(timezone.utc)
    if booking.locked_until < now:
        booking.status = BookingStatus.EXPIRED
        booking.cancelled_at = now
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El tiempo de retención temporal de 10 minutos ha expirado. "
            "La reserva ha sido cancelada automáticamente.",
        )
    return booking


async def create_wompi_checkout(
    db: AsyncSession, user_id: UUID, booking_id: UUID
) -> WompiCheckoutResponse:
    booking = await _get_payable_booking(db, user_id, booking_id)

    reference = wompi_gateway.build_reference(booking.id)
    amount_in_cents = wompi_gateway.amount_to_cents(booking.total_amount)
    signature = wompi_gateway.generate_integrity_signature(reference, amount_in_cents)

    return WompiCheckoutResponse(
        public_key=settings.WOMPI_PUBLIC_KEY,
        currency=settings.WOMPI_CURRENCY,
        amount_in_cents=amount_in_cents,
        reference=reference,
        signature=signature,
    )


async def verify_wompi_payment(
    db: AsyncSession, user_id: UUID, booking_id: UUID, transaction_id: str
) -> Payment:
    booking = await _get_payable_booking(db, user_id, booking_id)

    tx = await wompi_gateway.get_transaction(transaction_id)

    expected_reference = wompi_gateway.build_reference(booking.id)
    expected_cents = wompi_gateway.amount_to_cents(booking.total_amount)
    if tx.reference != expected_reference:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La transacción no corresponde a esta reserva.",
        )
    if tx.amount_in_cents != expected_cents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El monto de la transacción no coincide con el de la reserva.",
        )

    payment_result = await db.execute(
        select(Payment).where(Payment.booking_id == booking.id)
    )
    payment = payment_result.scalars().first()
    if not payment:
        payment = Payment(
            booking_id=booking.id,
            amount=booking.total_amount,
            status=PaymentStatus.PENDING,
            payment_method=tx.payment_method_type or "CARD",
            gateway_reference=tx.id,
        )
        db.add(payment)

    payment.gateway_reference = tx.id
    payment.payment_method = tx.payment_method_type or payment.payment_method

    if tx.is_approved:
        payment.status = PaymentStatus.APPROVED
        booking.status = BookingStatus.CONFIRMED
    else:
        payment.status = PaymentStatus.REJECTED

    await db.commit()
    await db.refresh(payment)
    await db.refresh(booking)
    return payment
