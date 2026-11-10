import enum
from uuid import uuid4
from sqlalchemy import (
    Column,
    Numeric,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class BookingStatus(str, enum.Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    space_id = Column(PG_UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=False)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    hourly_price_snapshot = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    # El tipo ya existe en PostgreSQL con el nombre "booking_status"
    status = Column(
        SQLEnum(BookingStatus, name="booking_status", create_type=False),
        default=BookingStatus.PENDING_PAYMENT,
        nullable=False,
    )
    locked_until = Column(
        DateTime(timezone=True), nullable=False
    )  # Retención temporal de 10 min
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    space = relationship("Space", back_populates="bookings")
    user = relationship("User", back_populates="bookings")
    payment = relationship("Payment", back_populates="booking", uselist=False)
