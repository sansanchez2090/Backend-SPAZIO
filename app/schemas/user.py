from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import uuid
from datetime import datetime


# Esquema base con atributos comunes
class UserBase(BaseModel):
    email: EmailStr
    full_name: str


# Esquema para cuando un usuario se registra (Entrada)
class UserCreate(UserBase):
    password: str = Field(
        ..., min_length=8, max_length=72, description="Mínimo 8 y máximo 72 caracteres"
    )


# Esquema para la respuesta de la API (Salida - Sin la contraseña)
class UserResponse(UserBase):
    id: uuid.UUID
    is_host: bool
    created_at: datetime

    class Config:
        from_attributes = (
            True  # Permite leer datos directamente desde modelos ORM de SQLAlchemy
        )


# Esquemas para el Login y Token JWT
class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
