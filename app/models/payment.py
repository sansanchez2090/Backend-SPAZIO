import enum
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import (
    Column,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REFUNDED = "REFUNDED"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    booking_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    gateway_reference = Column(String(255), nullable=True)
    payment_method = Column(String(50), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    # El tipo ya existe en PostgreSQL con el nombre "payment_status"
    status = Column(
        SQLEnum(PaymentStatus, name="payment_status", create_type=False),
        default=PaymentStatus.PENDING,
        nullable=False,
    )
    refund_amount = Column(Numeric(10, 2), default=Decimal("0.00"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relación bidireccional con Booking
    booking = relationship("Booking", back_populates="payment")
