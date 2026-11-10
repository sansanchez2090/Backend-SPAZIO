# app/schemas/space.py
import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.space import SpaceCategory
from shapely import wkb
import shapely.geometry


class SpaceBase(BaseModel):
    title: Optional[str] = Field(None, max_length=150)
    category: SpaceCategory = SpaceCategory.PARKING
    address: str = Field(..., max_length=255)
    neighborhood: Optional[str] = Field(None, max_length=100)
    conditions: Optional[str] = None
    price_per_hour: float = Field(..., gt=0)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    photos: List[str] = Field(default=[], max_length=3)


class SpaceCreate(SpaceBase):
    pass


class SpaceUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=150)
    category: Optional[SpaceCategory] = None
    address: Optional[str] = Field(None, max_length=255)
    neighborhood: Optional[str] = Field(None, max_length=100)
    conditions: Optional[str] = None
    price_per_hour: Optional[float] = Field(None, gt=0)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    photos: Optional[List[str]] = Field(None, max_length=3)
    is_active: Optional[bool] = None


class SpaceResponse(BaseModel):
    id: uuid.UUID
    host_id: uuid.UUID
    title: Optional[str]
    category: SpaceCategory
    address: str
    neighborhood: Optional[str]
    conditions: Optional[str]
    price_per_hour: float
    latitude: float
    longitude: float
    photos: List[str]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def extract_lat_lon_from_geometry(cls, values: Any) -> Any:
        """Extrae lat y lon del objeto WKB/GeoAlchemy2 almacenado en la BD."""
        # Si values es un modelo de SQLAlchemy (Space)
        if hasattr(values, "location") and values.location:
            try:
                # Convertimos el elemento WKBElement de GeoAlchemy2 a geometría de Shapely
                shape = wkb.loads(bytes(values.location.data))
                if isinstance(shape, shapely.geometry.Point):
                    # En PostGIS POINT guardamos (Longitud, Latitud)
                    setattr(values, "longitude", shape.x)
                    setattr(values, "latitude", shape.y)
            except Exception:
                pass
        return values


class SpaceCreateResponse(SpaceResponse):
    """Respuesta al publicar (RF-03): informa si la publicación activó el rol de anfitrión."""

    host_role_activated: bool = False


class AvailabilityWindow(BaseModel):
    """Horario (periodo de disponibilidad) mostrado en los resultados de búsqueda."""

    start_time: datetime
    end_time: datetime


class SpaceNearbyResponse(SpaceResponse):
    """Resultado de búsqueda por ubicación (RF-01): distancia, horario y precio."""

    distance_meters: float
    availabilities: List[AvailabilityWindow] = []
