from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.booking import BookingStatus


# --- Schemas para Reservas (RF-06, RF-07, RF-15) ---
class BookingCreate(BaseModel):
    space_id: UUID
    start_time: datetime
    end_time: datetime

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError(
                "La fecha/hora debe incluir zona horaria (ej. 2026-11-20T10:00:00-05:00)."
            )
        return v

    @field_validator("start_time")
    @classmethod
    def start_must_be_future(cls, v: datetime) -> datetime:
        if v <= datetime.now(timezone.utc):
            raise ValueError("La hora de inicio de la reserva debe ser futura.")
        return v

    @field_validator("end_time")
    @classmethod
    def validate_booking_range(cls, v: datetime, info) -> datetime:
        start = info.data.get("start_time")
        if start:
            if v <= start:
                raise ValueError(
                    "La fecha/hora de salida debe ser posterior a la entrada."
                )
            if start.minute != 0 or v.minute != 0:
                raise ValueError(
                    "Las reservas en SPAZIO deben ser por horas completas."
                )
        return v


class BookingResponse(BaseModel):
    id: UUID
    space_id: UUID
    user_id: UUID
    start_time: datetime
    end_time: datetime
    hourly_price_snapshot: Decimal
    total_amount: Decimal
    status: BookingStatus
    locked_until: datetime
    cancelled_at: Optional[datetime] = None
    created_at: datetime

    # Campos calculados informativos (RF-08 / RF-15)
    is_cancellable: Optional[bool] = True
    cancellation_reason: Optional[str] = None
    refund_percentage: Optional[int] = None
    refund_amount: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)
