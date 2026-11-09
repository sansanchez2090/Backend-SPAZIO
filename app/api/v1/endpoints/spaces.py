# app/api/v1/endpoints/spaces.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.space import SpaceCreate, SpaceUpdate, SpaceResponse
from app.services import space_service

router = APIRouter()


@router.post("/", response_model=SpaceResponse, status_code=status.HTTP_201_CREATED)
async def create_space(
    space_in: SpaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Publica un nuevo espacio (Solo para anfitriones con is_host=True)."""
    if not current_user.is_host:
        raise HTTPException(
            status_code=403, detail="Solo los anfitriones pueden publicar espacios."
        )
    return await space_service.create_space(db, space_in, current_user.id)


@router.get("/", response_model=List[SpaceResponse])
async def list_active_spaces(db: AsyncSession = Depends(get_db)):
    """Lista todos los espacios activos disponibles."""
    return await space_service.get_all_active_spaces(db)


@router.get("/my-spaces", response_model=List[SpaceResponse])
async def list_my_spaces(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Lista los espacios publicados por el anfitrión autenticado."""
    if not current_user.is_host:
        raise HTTPException(status_code=403, detail="Acceso denegado.")
    return await space_service.get_spaces_by_host(db, current_user.id)


@router.get("/nearby", response_model=List[SpaceResponse])
async def get_nearby_spaces(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius: float = Query(1000.0, gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Busca espacios en un radio determinado (en metros)."""
    return await space_service.search_spaces_nearby(db, latitude, longitude, radius)


@router.get("/{space_id}", response_model=SpaceResponse)
async def get_space_detail(space_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Obtiene los detalles de un espacio por su ID."""
    space = await space_service.get_space_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Espacio no encontrado.")
    return space


@router.put("/{space_id}", response_model=SpaceResponse)
async def update_space(
    space_id: uuid.UUID,
    space_in: SpaceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza un espacio (Solo el propietario anfitrión)."""
    space = await space_service.get_space_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Espacio no encontrado.")
    if space.host_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para modificar este espacio."
        )

    updated = await space_service.update_space(db, space_id, space_in)
    return updated


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_space(
    space_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Elimina un espacio (Solo el propietario anfitrión)."""
    space = await space_service.get_space_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Espacio no encontrado.")
    if space.host_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para eliminar este espacio."
        )

    await space_service.delete_space(db, space_id)
    return None
