import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña usando bcrypt directamente, truncando a 72 bytes."""
    pwd_bytes = plain_password.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]

    # bcrypt.checkpw requiere que ambos argumentos sean bytes
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Genera un hash seguro usando bcrypt directamente, truncando a 72 bytes."""
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]

    # Genera el salt y hashea la contraseña
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt
