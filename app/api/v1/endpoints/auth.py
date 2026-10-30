from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.user import UserCreate, UserResponse, UserLogin, Token
from app.services.user_service import (
    get_user_by_email,
    create_user,
    authenticate_user,
)
from app.api.v1.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Registra un nuevo usuario validando que el correo no esté en uso."""
    existing_user = await get_user_by_email(db, user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya se encuentra registrado.",
        )
    return await create_user(db, user_in)


@router.post(
    "/login", response_model=Token, summary="Iniciar sesión y obtener token JWT"
)
async def login(
    user_in: UserLogin, db: AsyncSession = Depends(get_db)
):  # OJO: Usamos UserLogin para JSON body limpio
    """Autentica las credenciales y devuelve un token JWT Bearer."""
    user = await authenticate_user(db, user_in.email, user_in.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtener perfil del usuario autenticado",
)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Devuelve los datos del usuario dueño del token JWT actual."""
    return current_user
