from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from app.models.payment import PaymentStatus


class PaymentProcess(BaseModel):
    booking_id: UUID
    payment_method: str  # Ej: "CARD", "PSE", "NEQUI"
    gateway_reference: Optional[str] = None  # El ID de Wompi o referencia simulada
    # Un valor desconocido responde 422 en vez de dejar el pago en PENDING
    simulated_status: Literal["APPROVED", "REJECTED"] = "APPROVED"


class PaymentResponse(BaseModel):
    id: UUID
    booking_id: UUID
    gateway_reference: Optional[str] = None
    payment_method: Optional[str] = None
    amount: Decimal
    status: PaymentStatus
    refund_amount: Decimal
    created_at: Any  # o datetime según tu importación

    model_config = ConfigDict(from_attributes=True)


class WompiCheckoutResponse(BaseModel):
    public_key: str
    currency: str
    amount_in_cents: int
    reference: str
    signature: str
    redirect_url: Optional[str] = None


class WompiPaymentVerify(BaseModel):
    booking_id: UUID
    transaction_id: str
