from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    users,
    spaces,
    availabilities,
    bookings,
    payments,
    geocoding,
)

api_router = APIRouter()


api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
api_router.include_router(users.router, prefix="/users", tags=["Usuarios"])
api_router.include_router(spaces.router, prefix="/spaces", tags=["Espacios"])
api_router.include_router(
    availabilities.router, prefix="/availabilities", tags=["Disponibilidad de Espacios"]
)
api_router.include_router(bookings.router, prefix="/bookings", tags=["Reservas"])
api_router.include_router(
    payments.router, prefix="/payments", tags=["Pagos y Pasarela (Wompi)"]
)
api_router.include_router(
    geocoding.router, prefix="/geocode", tags=["Geocodificación (OpenStreetMap)"]
)
