from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, status

from app.models.availability import Availability
from app.schemas.availability import AvailabilityCreate
from app.models.space import Space


async def create_availability_period(
    db: AsyncSession, user_id: UUID, payload: AvailabilityCreate
) -> Availability:
    # 1. Verificar que el espacio exista
    space_query = select(Space).where(Space.id == payload.space_id)
    space_result = await db.execute(space_query)
    space = space_result.scalars().first()

    if not space:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El espacio físico especificado no existe.",
        )

    # 2. Validar que el usuario actual sea el propietario (Anfitrión) del espacio
    if space.host_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes autorización para configurar la disponibilidad de un espacio que no te pertenece.",
        )

    # 3. Validar si ya existe un periodo traslapado en el mismo espacio
    overlap_query = select(Availability).where(
        and_(
            Availability.space_id == payload.space_id,
            Availability.start_time < payload.end_time,
            Availability.end_time > payload.start_time,
        )
    )
    result = await db.execute(overlap_query)
    existing_overlap = result.scalars().first()

    if existing_overlap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"El periodo de disponibilidad se traslapa con uno existente "
                f"({existing_overlap.start_time} - {existing_overlap.end_time})."
            ),
        )

    # 4. Crear el nuevo registro de disponibilidad
    new_availability = Availability(
        space_id=payload.space_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )

    db.add(new_availability)
    await db.commit()
    await db.refresh(new_availability)

    return new_availability


async def list_space_availabilities(db: AsyncSession, space_id: UUID):
    query = (
        select(Availability)
        .where(Availability.space_id == space_id)
        .order_by(Availability.start_time)
    )
    result = await db.execute(query)
    return result.scalars().all()


async def delete_availability_period(
    db: AsyncSession, availability_id: UUID, user_id: UUID
):
    # Buscar disponibilidad y su espacio para verificar propiedad
    query = (
        select(Availability, Space)
        .join(Space, Availability.space_id == Space.id)
        .where(Availability.id == availability_id)
    )
    result = await db.execute(query)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Periodo de disponibilidad no encontrado.",
        )

    availability, space = row
    if space.host_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para eliminar esta disponibilidad.",
        )

    await db.delete(availability)
    await db.commit()
    return {"message": "Periodo de disponibilidad eliminado exitosamente."}
