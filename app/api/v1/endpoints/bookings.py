from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingResponse
from app.services.booking_service import (
    create_booking,
    cancel_booking,
    list_user_bookings,
    get_booking_by_id,
)

router = APIRouter()


@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_new_booking(
    payload: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crea una reserva temporal (PENDING_PAYMENT) con una retención de 10 minutos (locked_until).
    Calcula automáticamente el monto total basado en el precio por hora del espacio.
    """
    return await create_booking(db=db, user_id=current_user.id, payload=payload)


# ⚠️ Las rutas fijas ('/me') SIEMPRE van antes que las dinámicas ('/{booking_id}')
@router.get("/me", response_model=List[BookingResponse], status_code=status.HTTP_200_OK)
async def list_my_bookings(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Lista el historial de reservas del usuario y calcula dinámicamente si cada reserva
    es cancelable y qué reembolso aplicaría (RF-08 / RF-15).
    """
    return await list_user_bookings(db=db, user_id=current_user.id)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking_detail(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtiene los detalles de una reserva específica del usuario."""
    return await get_booking_by_id(
        db=db, booking_id=booking_id, user_id=current_user.id
    )


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_user_booking(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancela una reserva del usuario autenticado (RF-08).
    Reembolso simulado: 100 % con 24 h o más de anticipación, 0 % con menos.
    """
    booking, refund_percentage, refund_amount = await cancel_booking(
        db=db, booking_id=booking_id, user_id=current_user.id
    )

    response_data = BookingResponse.model_validate(booking)
    response_data.is_cancellable = False
    response_data.cancellation_reason = "La reserva ha sido cancelada exitosamente."
    response_data.refund_percentage = refund_percentage
    response_data.refund_amount = refund_amount
    return response_data
