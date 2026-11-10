from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
import uuid

from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentProcess


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
