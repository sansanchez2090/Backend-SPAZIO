from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import Availability
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.space import Space
from app.schemas.booking import BookingCreate, BookingResponse


def compute_refund(booking: Booking, now: datetime) -> Tuple[int, Decimal]:
    """RN-12: 100 % si faltan 24 h o más para el inicio; 0 % si falta menos."""
    if (booking.start_time - now).total_seconds() >= 86400:
        return 100, booking.total_amount
    return 0, Decimal("0.00")


def _expire_if_lock_ran_out(booking: Booking, now: datetime) -> bool:
    """RF-07: una reserva sin pagar cuya retención venció pasa a EXPIRED."""
    if booking.status == BookingStatus.PENDING_PAYMENT and booking.locked_until < now:
        booking.status = BookingStatus.EXPIRED
        return True
    return False


async def list_user_bookings(db: AsyncSession, user_id: UUID) -> List[BookingResponse]:
    query = (
        select(Booking)
        .where(Booking.user_id == user_id)
        .order_by(Booking.created_at.desc())
    )
    result = await db.execute(query)
    bookings = result.scalars().all()

    now = datetime.now(timezone.utc)

    # Marca como expiradas las que se quedaron sin pagar (y recarga la lista)
    if any([_expire_if_lock_ran_out(b, now) for b in bookings]):
        await db.commit()
        result = await db.execute(query)
        bookings = result.scalars().all()

    response_list = []
    for booking in bookings:
        data = BookingResponse.model_validate(booking)

        if booking.status == BookingStatus.CONFIRMED and booking.start_time > now:
            pct, amount = compute_refund(booking, now)
            data.is_cancellable = True
            data.refund_percentage = pct
            data.refund_amount = amount
            data.cancellation_reason = (
                "Cancelable con reembolso del 100% (24 h o más de anticipación)."
                if pct == 100
                else "Cancelable sin reembolso (faltan menos de 24 horas para el inicio)."
            )
        elif booking.status == BookingStatus.CONFIRMED:
            data.is_cancellable = False
            data.cancellation_reason = (
                "No cancelable: el periodo de la reserva ya comenzó."
            )
        else:
            data.is_cancellable = False
            data.cancellation_reason = (
                f"No cancelable en estado actual ({booking.status.value})."
            )

        response_list.append(data)

    return response_list


async def get_booking_by_id(
    db: AsyncSession, booking_id: UUID, user_id: UUID
) -> Booking:
    query = select(Booking).where(Booking.id == booking_id, Booking.user_id == user_id)
    result = await db.execute(query)
    booking = result.scalars().first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada."
        )

    if _expire_if_lock_ran_out(booking, datetime.now(timezone.utc)):
        await db.commit()
        await db.refresh(booking)
    return booking


async def create_booking(
    db: AsyncSession, user_id: UUID, payload: BookingCreate
) -> Booking:
    # 1. Obtener el espacio y su precio por hora actual (Snapshot).
    #    with_for_update(): bloquea la fila del espacio hasta el commit, de modo que dos
    #    reservas simultáneas del mismo horario se procesen una tras otra y no se dupliquen.
    space_query = (
        select(Space)
        .where(Space.id == payload.space_id, Space.is_active == True)
        .with_for_update()
    )
    space_result = await db.execute(space_query)
    space = space_result.scalars().first()

    if not space:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El espacio físico no existe o no se encuentra activo.",
        )

    # 2. Validar que el rango solicitado esté dentro de un periodo de disponibilidad del anfitrión
    avail_query = select(Availability).where(
        and_(
            Availability.space_id == payload.space_id,
            Availability.start_time <= payload.start_time,
            Availability.end_time >= payload.end_time,
        )
    )
    avail_result = await db.execute(avail_query)
    matching_availability = avail_result.scalars().first()

    if not matching_availability:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El rango horario solicitado no está cubierto por la disponibilidad configurada del espacio.",
        )

    # 3. Validar que no exista otra reserva confirmada o pendiente vigente en ese mismo horario
    now = datetime.now(timezone.utc)

    # Cruce: (Booking.start_time < payload.end_time) AND (Booking.end_time > payload.start_time)
    # Si está PENDING_PAYMENT, solo cuenta mientras no haya expirado (locked_until > now)
    overlap_bookings_query = select(Booking).where(
        and_(
            Booking.space_id == payload.space_id,
            Booking.start_time < payload.end_time,
            Booking.end_time > payload.start_time,
            or_(
                Booking.status == BookingStatus.CONFIRMED,
                and_(
                    Booking.status == BookingStatus.PENDING_PAYMENT,
                    Booking.locked_until > now,
                ),
            ),
        )
    )
    conflict_result = await db.execute(overlap_bookings_query)
    if conflict_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El espacio ya se encuentra reservado o en proceso de pago para el rango de horas seleccionado.",
        )

    # 4. Cálculo financiero: horas completas × precio por hora (todo en Decimal)
    duration_delta = payload.end_time - payload.start_time
    hours = Decimal(duration_delta.total_seconds()) / Decimal(3600)
    total_amount = (hours * Decimal(str(space.price_per_hour))).quantize(
        Decimal("0.01")
    )

    # 5. Definir la retención temporal (10 minutos)
    locked_until_time = now + timedelta(minutes=10)

    # 6. Crear la reserva
    new_booking = Booking(
        space_id=payload.space_id,
        user_id=user_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        hourly_price_snapshot=space.price_per_hour,
        total_amount=total_amount,
        status=BookingStatus.PENDING_PAYMENT,
        locked_until=locked_until_time,
    )

    db.add(new_booking)
    await db.commit()
    await db.refresh(new_booking)

    return new_booking


async def cancel_booking(
    db: AsyncSession, booking_id: UUID, user_id: UUID
) -> Tuple[Booking, Optional[int], Decimal]:
    """Devuelve (reserva, % de reembolso o None si no hubo pago, monto reembolsado)."""
    query = select(Booking).where(Booking.id == booking_id, Booking.user_id == user_id)
    result = await db.execute(query)
    booking = result.scalars().first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La reserva no existe o no pertenece al usuario actual.",
        )

    now = datetime.now(timezone.utc)
    if _expire_if_lock_ran_out(booking, now):
        await db.commit()
        await db.refresh(booking)

    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La reserva ya se encuentra cancelada.",
        )
    if booking.status == BookingStatus.EXPIRED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La reserva ya ha expirado por tiempo de retención.",
        )

    # RF-08 / RN-12: 100 % con 24 h o más; 0 % con menos. Solo antes de que empiece.
    refund_percentage: Optional[int] = None
    refund_amount = Decimal("0.00")
    if booking.status == BookingStatus.CONFIRMED:
        if booking.start_time <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No es posible cancelar la reserva: el periodo ya comenzó.",
            )
        refund_percentage, refund_amount = compute_refund(booking, now)

    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = now

    payment_res = await db.execute(
        select(Payment).where(Payment.booking_id == booking.id)
    )
    payment = payment_res.scalars().first()
    if payment and payment.status == PaymentStatus.APPROVED:
        payment.refund_amount = refund_amount
        if refund_amount > 0:  # con 0 % el pago queda APPROVED (no se devolvió dinero)
            payment.status = PaymentStatus.REFUNDED

    await db.commit()
    await db.refresh(booking)
    return booking, refund_percentage, refund_amount
