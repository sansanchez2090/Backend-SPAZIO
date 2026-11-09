from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.user import UserLogin, Token
from app.services.user_service import authenticate_user

router = APIRouter()


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

    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}
