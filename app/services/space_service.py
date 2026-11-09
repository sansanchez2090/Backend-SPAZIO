# app/services/space_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from app.models.space import Space
from app.schemas.space import SpaceCreate, SpaceUpdate
from typing import List, Optional
import uuid


async def create_space(
    db: AsyncSession, space_in: SpaceCreate, host_id: uuid.UUID
) -> Space:
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
    await db.delete(db_space)
    await db.commit()
    return True


async def search_spaces_nearby(
    db: AsyncSession, latitude: float, longitude: float, radius_meters: float = 1000.0
) -> List[Space]:
    user_point_wkt = f"SRID=4326;POINT({longitude} {latitude})"
    stmt = select(Space).where(
        func.ST_DWithin(
            Space.location, func.ST_GeographyFromText(user_point_wkt), radius_meters
        ),
        Space.is_active == True,
    )
    result = await db.execute(stmt)
    return result.scalars().all()
