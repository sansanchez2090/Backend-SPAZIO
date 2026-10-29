from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

# Engine asíncrono de SQLAlchemy
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,  # Cambiar a False en producción si no deseas ver los logs de SQL
    future=True,
)

# Fabrica de sesiones asíncronas
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# Clase Base para los Modelos ORM
class Base(DeclarativeBase):
    pass


# Dependencia inyectable en Endpoints de FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()