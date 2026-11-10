from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.payment import PaymentProcess
from app.models.user import User
from app.services.payment_service import process_simulated_payment
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.post("/process", status_code=status.HTTP_200_OK)
async def process_payment(
    payload: PaymentProcess,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # Usuario autenticado
):
    # Simulamos o procesamos el pago llamando a tu servicio
    payment = await process_simulated_payment(
        db=db, user_id=current_user.id, payload=payload
    )

    return {
        "message": "Proceso de pago ejecutado con éxito",
        "payment_id": payment.id,
        "status": payment.status,
        "gateway_reference": payment.gateway_reference,
    }
