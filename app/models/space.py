# app/models/space.py (o app/models/enums.py)
import enum
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Boolean, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from app.core.database import Base
import uuid
from datetime import datetime, timezone


class SpaceCategory(str, enum.Enum):
    PARKING = "PARKING"
    STORAGE = "STORAGE"
    OFFICES = "OFFICES"
    EVENTS = "EVENTS"
    SPORTS = "SPORTS"
    STUDIOS = "STUDIOS"
    COMMERCIAL = "COMMERCIAL"


class Space(Base):
    __tablename__ = "spaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    host_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Mapeamos usando el Enum de Python y el tipo existente en PostgreSQL
    category = Column(
        Enum(SpaceCategory, name="space_category", create_type=False),
        nullable=False,
        default=SpaceCategory.PARKING,
    )

    title = Column(String(150), nullable=True)
    address = Column(String(255), nullable=False)
    neighborhood = Column(String(100), nullable=True)
    location = Column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    price_per_hour = Column(Float, nullable=False)
    conditions = Column(Text, nullable=True)
    photos = Column(ARRAY(String), default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    availabilities = relationship(
        "Availability", back_populates="space", cascade="all, delete-orphan"
    )
    bookings = relationship(
        "Booking", back_populates="space", cascade="all, delete-orphan"
    )
    host = relationship("User", back_populates="spaces")
