"""Configuración central de la aplicación.

Todo lo que cambia entre entornos (dev, test, prod) vive aquí y se lee
desde variables de entorno (archivo .env). Esto es el principio 12-factor.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "Ecommerce API"
    APP_VERSION: str = "0.2.0"

    # Por defecto SQLite para arrancar sin instalar nada.
    # En producción se usa PostgreSQL: postgresql+psycopg://user:pass@host:5432/db
    DATABASE_URL: str = "sqlite:///./ecommerce.db"

    JWT_SECRET: str = "dev-secret-change-me-please-use-a-long-random-value"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Cache ---
    # Si está vacío o Redis no responde, se usa una caché en memoria.
    REDIS_URL: str = ""
    CACHE_TTL_SECONDS: int = 60

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 120

    # --- Observabilidad ---
    LOG_LEVEL: str = "INFO"


settings = Settings()
