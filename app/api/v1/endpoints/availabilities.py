from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.core.database import get_db  # Dependencia para obtener la sesión de BD async
from app.api.v1.deps import get_current_user  # Supone autenticación JWT existente
from app.models.user import User
from app.schemas.availability import AvailabilityCreate, AvailabilityResponse
from app.services.availability_service import (
    create_availability_period,
    list_space_availabilities,
    delete_availability_period,
)

router = APIRouter()


@router.post(
    "/", response_model=AvailabilityResponse, status_code=status.HTTP_201_CREATED
)
async def create_availability(
    payload: AvailabilityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registra un nuevo periodo de disponibilidad para un espacio validando propiedad y traslapes.
    """
    return await create_availability_period(
        db=db, user_id=current_user.id, payload=payload
    )


@router.get("/space/{space_id}", response_model=List[AvailabilityResponse])
async def get_space_availabilities(space_id: UUID, db: AsyncSession = Depends(get_db)):
    """Lista todos los periodos de disponibilidad configurados para un espacio."""
    return await list_space_availabilities(db=db, space_id=space_id)


@router.delete("/{availability_id}", status_code=status.HTTP_200_OK)
async def remove_availability(
    availability_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Elimina un periodo de disponibilidad validando propiedad del anfitrión."""
    return await delete_availability_period(
        db=db, availability_id=availability_id, user_id=current_user.id
    )
