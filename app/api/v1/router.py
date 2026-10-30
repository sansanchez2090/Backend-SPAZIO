from fastapi import APIRouter
from app.api.v1.endpoints import auth

api_router = APIRouter()

# Incluir módulo de autenticación
api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
