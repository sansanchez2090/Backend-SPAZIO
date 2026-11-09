# app/api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Registra un nuevo usuario en el sistema."""
    existing_user = await user_service.get_user_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya se encuentra registrado.",
        )
    user = await user_service.create_user(db, user_in)
    return user


@router.get("/me", response_model=UserResponse)
async def read_user_me(current_user: User = Depends(get_current_user)):
    """Obtiene los datos del perfil del usuario actualmente autenticado."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_user_me(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza la información del perfil del usuario autenticado."""
    updated_user = await user_service.update_user(
        db, user_id=current_user.id, user_in=user_in
    )
    return updated_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_me(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Elimina la cuenta del usuario autenticado (limpieza de perfil)."""
    await user_service.delete_user(db, user_id=current_user.id)
    return None
