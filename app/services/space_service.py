# app/services/space_service.py
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import Availability
from app.models.booking import Booking, BookingStatus
from app.models.space import Space, SpaceCategory
from app.schemas.space import (
    AvailabilityWindow,
    SpaceCreate,
    SpaceNearbyResponse,
    SpaceResponse,
    SpaceUpdate,
)


async def create_space(
    db: AsyncSession, space_in: SpaceCreate, host_id: uuid.UUID
) -> Space:
    """Publica un espacio. El rol de anfitrión (is_host) lo activa el trigger
    `trg_activate_host_role` de la BD al insertar la primera publicación (RF-03)."""
    point = Point(space_in.longitude, space_in.latitude)
    wkb_element = from_shape(point, srid=4326)

    db_space = Space(
        host_id=host_id,
        category=space_in.category,
        title=space_in.title,
        address=space_in.address,
        neighborhood=space_in.neighborhood,
        conditions=space_in.conditions,
        price_per_hour=space_in.price_per_hour,
        photos=space_in.photos,
        location=wkb_element,
    )
    db.add(db_space)
    await db.commit()
    await db.refresh(db_space)
    return db_space


async def get_space_by_id(db: AsyncSession, space_id: uuid.UUID) -> Optional[Space]:
    result = await db.execute(select(Space).where(Space.id == space_id))
    return result.scalar_one_or_none()


async def get_all_active_spaces(db: AsyncSession) -> List[Space]:
    result = await db.execute(select(Space).where(Space.is_active == True))
    return result.scalars().all()


async def get_spaces_by_host(db: AsyncSession, host_id: uuid.UUID) -> List[Space]:
    result = await db.execute(select(Space).where(Space.host_id == host_id))
    return result.scalars().all()


async def update_space(
    db: AsyncSession, space_id: uuid.UUID, space_in: SpaceUpdate
) -> Optional[Space]:
    db_space = await get_space_by_id(db, space_id)
    if not db_space:
        return None

    update_data = space_in.model_dump(exclude_unset=True)

    # Si se actualizan latitud o longitud, recalculamos el punto geográfico PostGIS
    lat = update_data.pop("latitude", None)
    lon = update_data.pop("longitude", None)
    if lat is not None and lon is not None:
        point = Point(lon, lat)
        db_space.location = from_shape(point, srid=4326)

    for field, value in update_data.items():
        setattr(db_space, field, value)

    await db.commit()
    await db.refresh(db_space)
    return db_space


async def delete_space(db: AsyncSession, space_id: uuid.UUID) -> bool:
    db_space = await get_space_by_id(db, space_id)
    if not db_space:
        return False

    # No se puede borrar un espacio con reservas vigentes (pagadas o en proceso de pago)
    now = datetime.now(timezone.utc)
    active = await db.execute(
        select(Booking.id)
        .where(
            Booking.space_id == space_id,
            or_(
                and_(Booking.status == BookingStatus.CONFIRMED, Booking.end_time > now),
                and_(
                    Booking.status == BookingStatus.PENDING_PAYMENT,
                    Booking.locked_until > now,
                ),
            ),
        )
        .limit(1)
    )
    if active.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar un espacio con reservas vigentes "
            "(confirmadas o en proceso de pago).",
        )

    await db.delete(db_space)
    await db.commit()
    return True


async def search_spaces_nearby(
    db: AsyncSession,
    latitude: float,
    longitude: float,
    radius_meters: float = 1000.0,
    category: Optional[SpaceCategory] = None,
) -> List[SpaceNearbyResponse]:
    """RF-01: espacios activos con horario disponible dentro del radio, ordenados por
    distancia, con distancia (m), horario (periodos vigentes) y precio."""
    now = datetime.now(timezone.utc)
    user_point = func.ST_GeographyFromText(f"SRID=4326;POINT({longitude} {latitude})")
    distance = func.ST_Distance(Space.location, user_point).label("distance_meters")

    # "Disponible" = tiene al menos un periodo de disponibilidad que aún no termina.
    # (Para listar también espacios sin horario, elimina esta condición.)
    has_future_availability = exists().where(
        Availability.space_id == Space.id, Availability.end_time > now
    )

    stmt = (
        select(Space, distance)
        .where(
            func.ST_DWithin(Space.location, user_point, radius_meters),
            Space.is_active == True,
            has_future_availability,
        )
        .order_by(distance)
    )
    if category is not None:
        stmt = stmt.where(Space.category == category)

    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    # Horario: periodos vigentes de todos los espacios encontrados, en una sola consulta
    space_ids = [space.id for space, _ in rows]
    avail_result = await db.execute(
        select(Availability)
        .where(Availability.space_id.in_(space_ids), Availability.end_time > now)
        .order_by(Availability.start_time)
    )
    windows = defaultdict(list)
    for a in avail_result.scalars().all():
        windows[a.space_id].append(
            AvailabilityWindow(start_time=a.start_time, end_time=a.end_time)
        )

    results = []
    for space, dist in rows:
        data = SpaceResponse.model_validate(space).model_dump()
        results.append(
            SpaceNearbyResponse(
                **data,
                distance_meters=round(float(dist), 1),
                availabilities=windows.get(space.id, []),
            )
        )
    return results
