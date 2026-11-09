from fastapi import APIRouter
from app.api.v1.endpoints import auth, users

api_router = APIRouter()

# Incluir módulo de autenticación
api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
api_router.include_router(users.router, prefix="/users", tags=["Usuarios"])
