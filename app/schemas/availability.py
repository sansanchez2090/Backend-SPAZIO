from datetime import datetime, timezone
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator


# --- Schemas para Disponibilidad (RF-05) ---
class AvailabilityCreate(BaseModel):
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

    @field_validator("end_time")
    @classmethod
    def validate_timespan(cls, v: datetime, info) -> datetime:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("La fecha/hora de fin debe ser posterior a la de inicio.")
        # Solo se rechaza un periodo que YA TERMINÓ; uno vigente que empezó antes es válido.
        if v <= datetime.now(timezone.utc):
            raise ValueError("El periodo de disponibilidad ya terminó.")
        return v


class AvailabilityResponse(BaseModel):
    id: UUID
    space_id: UUID
    start_time: datetime
    end_time: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
