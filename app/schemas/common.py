"""Schemas comunes reutilizables (respuestas de error, salud, etc.)."""

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    """Formato estándar de error de FastAPI: `{"detail": "..."}`."""

    detail: str

    model_config = ConfigDict(
        json_schema_extra={"example": {"detail": "El recurso no fue encontrado"}}
    )


class HealthResponse(BaseModel):
    status: str
    app: str | None = None
    version: str | None = None

    model_config = ConfigDict(
        json_schema_extra={"example": {"status": "ok", "app": "Ecommerce API", "version": "0.2.0"}}
    )
