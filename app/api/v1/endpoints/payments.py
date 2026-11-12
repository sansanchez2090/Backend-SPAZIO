from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.payment import PaymentProcess, WompiCheckoutResponse, WompiPaymentVerify
from app.models.user import User
from app.services.payment_service import (
    process_simulated_payment,
    create_wompi_checkout,
    verify_wompi_payment,
)
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.post(
    "/checkout/{booking_id}",
    response_model=WompiCheckoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Generar firma del Widget de Wompi para una reserva",
)
async def wompi_checkout(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_wompi_checkout(
        db=db, user_id=current_user.id, booking_id=booking_id
    )


@router.post(
    "/verify",
    status_code=status.HTTP_200_OK,
    summary="Verificar en Wompi la transacción y confirmar la reserva",
)
async def wompi_verify(
    payload: WompiPaymentVerify,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = await verify_wompi_payment(
        db=db,
        user_id=current_user.id,
        booking_id=payload.booking_id,
        transaction_id=payload.transaction_id,
    )
    return {
        "message": "Verificación de pago completada.",
        "payment_id": payment.id,
        "status": payment.status,
        "gateway_reference": payment.gateway_reference,
    }


@router.post("/process", status_code=status.HTTP_200_OK)
async def process_payment(
    payload: PaymentProcess,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = await process_simulated_payment(
        db=db, user_id=current_user.id, payload=payload
    )

    return {
        "message": "Proceso de pago ejecutado con éxito",
        "payment_id": payment.id,
        "status": payment.status,
        "gateway_reference": payment.gateway_reference,
    }
