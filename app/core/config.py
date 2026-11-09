from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "SPAZIO API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Base de Datos (Supabase PostgreSQL via Asyncpg)
    DATABASE_URL: str

    # Seguridad / JWT
    SECRET_KEY: str = "spazio_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días

    # Pasarela de Pagos (Wompi Sandbox)
    WOMPI_PUBLIC_KEY: str = ""
    WOMPI_PRIVATE_KEY: str = ""

    # Supabase Storage
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()