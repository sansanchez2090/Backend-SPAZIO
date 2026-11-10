from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
import uuid
from datetime import datetime


# Esquema base con atributos comunes
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    is_host: bool = False


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

    model_config = ConfigDict(from_attributes=True)


# Esquemas para el Login y Token JWT
class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_host: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)
